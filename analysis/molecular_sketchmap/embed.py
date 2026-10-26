#!/usr/bin/env python3
"""Average SOAP molecular distances and genuine scikit-matter sketch-map."""
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from ase import Atoms
from ase.data import atomic_numbers
from dscribe.descriptors import SOAP
from scipy.linalg import orthogonal_procrustes
from scipy.spatial.distance import pdist, squareform, cdist
from scipy.stats import spearmanr
from sklearn.manifold import trustworthiness
from skmatter.decomposition import SketchMap
from threadpoolctl import threadpool_limits

from extract_molecules import BASE, write_json


def sigmoid(distances, sigma, a=1., b=4.):
    return 1 - (1 + (2**(a/b) - 1) * (distances/sigma)**a)**(-b/a)


def classical_mds(distance):
    n = len(distance)
    j = np.eye(n) - np.ones((n, n))/n
    eig, vec = np.linalg.eigh(-.5 * j @ (distance**2) @ j)
    return vec[:, -2:] * np.sqrt(np.maximum(eig[-2:], 0))


def retention(a, b, k=10):
    aa, bb = a.copy(), b.copy()
    np.fill_diagonal(aa, np.inf); np.fill_diagonal(bb, np.inf)
    return float(np.mean([len(set(i) & set(j))/k for i, j in zip(np.argsort(aa, axis=1)[:, :k], np.argsort(bb, axis=1)[:, :k])]))


def metrics(distance, embedding, sigma):
    low = squareform(pdist(embedding))
    upper = np.triu_indices(len(distance), 1)
    delta = sigmoid(distance, sigma) - sigmoid(low, sigma)
    return {"sigmoid_pair_mse": float(np.mean(delta[upper]**2)),
            "distance_spearman": float(spearmanr(distance[upper], low[upper]).statistic),
            "trustworthiness_k10": float(trustworthiness(distance, embedding, n_neighbors=10, metric="precomputed")),
            "neighbor_retention_k10": retention(distance, low)}


def gradient_max(distance, embedding, sigma):
    low = cdist(embedding, embedding)
    q = 2**.25 - 1
    derivative = 4*q/sigma * (1 + q*low/sigma)**-5
    coefficients = (sigmoid(distance, sigma) - sigmoid(low, sigma))*derivative/np.maximum(low, 1e-12)
    np.fill_diagonal(coefficients, 0)
    grad = -2/(len(distance)*(len(distance)-1)/2) * (coefficients.sum(axis=1)[:, None]*embedding - coefficients @ embedding)
    return float(np.max(np.abs(grad)))


def main():
    extraction = pd.read_csv(BASE / "tables/extraction.csv").sort_values("dataset_id")
    valid = extraction[extraction.included].copy().reset_index(drop=True)
    records = [json.loads((BASE / "molecules" / (identifier + ".json")).read_text()) for identifier in valid.dataset_id]
    atoms = [Atoms(r["symbols"], positions=r["coordinates_angstrom"]) for r in records]
    species = sorted({s for r in records for s in r["symbols"]}, key=atomic_numbers.get)
    settings = {"descriptor": {"name": "DScribe SOAP", "species": species, "periodic": False, "r_cut": 4.5, "n_max": 6, "l_max": 4, "sigma": .4, "average": "outer", "rbf": "gto", "dtype": "float64", "normalization": "L2 per molecule after outer average; no per-feature standardization", "kernel": "K_ij=(x_i dot x_j)^2", "distance": "sqrt(max(0,2-2*K_ij))", "centres": "all atoms including hydrogen", "molecular_size": "No explicit atom-count or mass feature; average local environments, including composition and geometry inside 4.5 A; mass is a display variable only", "chirality": "SOAP is reflection invariant; enantiomers cannot be separated by these descriptors"},
                "sketchmap": {"implementation": "skmatter.decomposition.SketchMap", "dissimilarity": "precomputed", "n_components": 2, "a_high": 1., "b_high": 4., "a_low": 1., "b_low": 4., "mds_opt_steps": 100, "max_iter": 2500, "global_opt_steps": 5, "global_optimizer": "gradient", "mixing_schedule": "auto", "mixing_ratio": 0., "weights": "equal per dataset; archive counts never enter descriptors or optimization", "initialization_seeds": [0, 17, 41, 83, 137], "initialization": "Classical MDS; seed 0 unperturbed, other seeds add Gaussian noise with SD 0.25 times coordinate RMS", "sigma_rule": "0.8 times mode of positive pair distances, histogram bins=clip(Freedman-Diaconis count,30,80)", "sigma_sensitivity_factors": [.8, 1.2]},
                "versions": {n: importlib.metadata.version(n) for n in ["ase", "dscribe", "skmatter", "scipy", "scikit-learn", "rdkit", "pandas", "numpy", "matplotlib", "fonttools", "pypdf", "Pillow", "threadpoolctl"]},
                "documentation": {"sketchmap": "https://scikit-matter.readthedocs.io/en/stable/references/decomposition.html#sketchmap", "soap": "https://singroup.github.io/dscribe/latest/tutorials/descriptors/soap.html", "molecular_sketchmap_paper": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5289135/", "shelx": "https://shelx.uni-goettingen.de/shelxl_html.php"}}
    soap = SOAP(**{k: v for k, v in settings["descriptor"].items() if k in {"species", "periodic", "r_cut", "n_max", "l_max", "sigma", "average", "rbf", "dtype"}})
    print(f"SOAP: {len(atoms)} molecules; elements {species}; {soap.get_number_of_features()} features", flush=True)
    vectors = np.asarray(soap.create(atoms, n_jobs=1))
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    kernel = np.clip(vectors @ vectors.T, -1, 1)**2
    distance = np.sqrt(np.maximum(0, 2-2*kernel)); np.fill_diagonal(distance, 0)
    settings["descriptor"]["features"] = vectors.shape[1]
    # Empirical invariance check uses actual extracted coordinates, no atom edits.
    test = atoms[len(atoms)//2].copy()
    test.positions += [2.37, -.92, 1.41]
    test.rotate(37, [1, 2, 3], rotate_cell=False)
    test = test[np.random.default_rng(419).permutation(len(test))]
    test_vector = soap.create(test); test_vector /= np.linalg.norm(test_vector)
    invariance_error = float(np.max(np.abs(test_vector - vectors[len(atoms)//2])))
    if invariance_error > 1e-6: raise AssertionError("SOAP invariance check failed")
    values = distance[np.triu_indices(len(distance), 1)]
    positive = values[values > 1e-7]
    bins = int(np.clip(len(np.histogram_bin_edges(positive, bins="fd"))-1, 30, 80))
    hist, edges = np.histogram(positive, bins=bins)
    mode = float((edges[hist.argmax()] + edges[hist.argmax()+1])/2)
    sigma = .8 * mode
    settings["sketchmap"].update({"sigma": sigma, "distance_histogram_mode": mode, "distance_histogram_bins": bins})
    settings["validation"] = {"invariance_max_abs_error": invariance_error, "number_of_datasets": len(valid), "source_extraction_csv_sha256": hashlib.sha256((BASE / "tables/extraction.csv").read_bytes()).hexdigest(), "sketchmap_implementation_sha256": hashlib.sha256(Path(inspect.getsourcefile(SketchMap)).read_bytes()).hexdigest()}
    np.savez_compressed(BASE / "data/molecular_descriptors.npz", dataset_ids=valid.dataset_id.to_numpy(dtype=str), normalized_soap=vectors, soap_kernel=kernel, distances=distance)
    pd.DataFrame(distance, index=valid.dataset_id, columns=valid.dataset_id).rename_axis("dataset_id").to_csv(BASE / "tables/molecular_distances.csv")
    write_json(BASE / "parameters.json", settings)
    initial = classical_mds(distance)
    runs, embeddings = [], []
    arguments = {k: settings["sketchmap"][k] for k in ["n_components", "dissimilarity", "a_high", "b_high", "a_low", "b_low", "mds_opt_steps", "max_iter", "global_opt_steps", "global_optimizer", "mixing_ratio", "mixing_schedule"]}
    with threadpool_limits(limits=1):
        for seed in settings["sketchmap"]["initialization_seeds"]:
            start = initial.copy()
            if seed: start += np.random.default_rng(seed).normal(size=start.shape) * .25 * np.sqrt(np.mean(start**2))
            estimator = SketchMap(**arguments, sigma=sigma, init=start)
            clock = time.monotonic(); embedding = estimator.fit_transform(distance)
            result = {"kind": "initialization", "seed": seed, "sigma": sigma, "iterations": int(estimator.n_iter_), "library_stress": float(estimator.stress_), "seconds": time.monotonic()-clock, **metrics(distance, embedding, sigma)}
            runs.append(result); embeddings.append(embedding)
            print(json.dumps(result), flush=True)
        selected = min(range(len(runs)), key=lambda i: runs[i]["sigmoid_pair_mse"])
        best = embeddings[selected]
        refine_args = arguments | {"mds_opt_steps": 0, "global_opt_steps": 0, "mixing_schedule": None, "max_iter": 5000}
        refine = SketchMap(**refine_args, sigma=sigma, init=best)
        polished = refine.fit_transform(distance)
        before, after = metrics(distance, best, sigma), metrics(distance, polished, sigma)
        if after["sigmoid_pair_mse"] <= before["sigmoid_pair_mse"]: best = polished
        stability = []
        best_c = best-best.mean(axis=0)
        for run, embedding in zip(runs, embeddings):
            centered = embedding-embedding.mean(axis=0)
            rotation, _ = orthogonal_procrustes(centered, best_c)
            aligned = centered @ rotation
            stability.append({"seed": run["seed"], "procrustes_relative_rms_no_scaling": float(np.sqrt(np.mean((aligned-best_c)**2)/np.mean(best_c**2))), "distance_spearman_to_selected": float(spearmanr(pdist(embedding), pdist(best)).statistic), "neighbor_retention_k10_to_selected": retention(squareform(pdist(embedding)), squareform(pdist(best)))})
        for factor in settings["sketchmap"]["sigma_sensitivity_factors"]:
            estimator = SketchMap(**arguments, sigma=sigma*factor, init=initial)
            clock = time.monotonic(); embedding = estimator.fit_transform(distance)
            runs.append({"kind": "sigma_sensitivity", "seed": 0, "sigma": sigma*factor, "sigma_factor": factor, "iterations": int(estimator.n_iter_), "library_stress": float(estimator.stress_), "seconds": time.monotonic()-clock, **metrics(distance, embedding, sigma*factor), "distance_spearman_to_selected": float(spearmanr(pdist(embedding), pdist(best)).statistic), "neighbor_retention_k10_to_selected": retention(squareform(pdist(embedding)), squareform(pdist(best)))})
            print(json.dumps(runs[-1]), flush=True)
    # Canonical page orientation: rigid PCA rotation only, no rescaling or jitter.
    centered = best-best.mean(axis=0); _, _, rotation = np.linalg.svd(centered, full_matrices=False)
    best = centered @ rotation.T
    if np.corrcoef(best[:, 0], valid.selected_molar_mass_g_mol)[0, 1] < 0: best[:, 0] *= -1
    valid["sketchmap_x"], valid["sketchmap_y"] = best.T
    valid["marker_area_pt2"] = 1.8*np.sqrt(valid.structure_count)
    valid["marker_area_rule"] = "1.8 * sqrt(archived structure files), square points; compressed area mapping"
    complete = extraction.merge(valid[["dataset_id", "sketchmap_x", "sketchmap_y", "marker_area_pt2", "marker_area_rule"]], on="dataset_id", how="left", validate="one_to_one")
    complete.to_csv(BASE / "tables/dataset_embedding.csv", index=False)
    pd.DataFrame(runs).to_csv(BASE / "tables/optimization_runs.csv", index=False)
    pd.DataFrame(stability).to_csv(BASE / "tables/initialization_stability.csv", index=False)
    np.savez_compressed(BASE / "data/sketchmap_runs.npz", dataset_ids=valid.dataset_id.to_numpy(dtype=str), selected_embedding=best, initialization_embeddings=np.asarray(embeddings), initialization_seeds=np.asarray(settings["sketchmap"]["initialization_seeds"]))
    result = {"selected_initialization_seed": runs[selected]["seed"], "metrics": metrics(distance, best, sigma), "refinement": {"iterations": int(refine.n_iter_), "stress_before": before["sigmoid_pair_mse"], "stress_after": after["sigmoid_pair_mse"], "max_abs_stress_gradient": gradient_max(distance, best, sigma)}, "initialization_stability": stability, "parameters": "parameters.json", "sigma_sensitivity": [r for r in runs if r["kind"] == "sigma_sensitivity"], "invariance_max_abs_error": invariance_error, "sample_weights": "All datasets equal; counts used only for marker areas", "jitter": "None; coincident or near-coincident points retained"}
    write_json(BASE / "data/embedding_summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__": main()
