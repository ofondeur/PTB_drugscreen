#!/usr/bin/env python
"""
Script to run a gridsearch on the final model (XGB...) using already selected features.
"""
import seaborn as sns
import matplotlib.pyplot as plt
import os
import sys
sys.path.insert(0, '../Stabl')
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
import argparse
from sklearn.metrics import mean_absolute_error,mean_squared_error
import shutil
import itertools
# Import scikit-learn modules
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor
from stabl.cross_validation_drug_vs_dmso import cv_on_existing_feats
from sklearn.ensemble import RandomForestRegressor
from stabl_utils import get_estimators,split_features_by_stim,get_stims,process_data

def main():
    parser = argparse.ArgumentParser(description="Run STABL Regression CV with configurable inputs.")
    parser.add_argument(
        "--features_path",
        required=True,
        help="Path to the input features CSV file (wide format)."
    )
    parser.add_argument(
        "--fold_feats_path",
        required=True,
        help="Path to the features selected per fold."
    )
    parser.add_argument(
        "--model_chosen",
        required=True,
        help="Model chosen for the regression (put None if classification)."
    )

    parser.add_argument(
        "--results_dir",
        required=True,
        help="Base directory where results subdirectories will be created."
    )
    parser.add_argument(
        "--artificial_type",
        required=True,
        choices=["random_permutation", "knockoff"],
        help="Type of artificial features for STABL ('random_permutation' or 'knockoff')."
    )
    args = parser.parse_args()

    features_path = args.features_path
    artificial_type_arg = args.artificial_type
    model_chosen=args.model_chosen
    outcome_path = "../Data/outcome_table_all_pre.csv"


    results_path=args.results_dir
    fold_feats_path=args.fold_feats_path
    print(f"Input Features: {features_path}")
    print(f"Results will be saved to: {results_path}")
    print(f"Using STABL artificial type: {artificial_type_arg}")
    print(f"Using fold features from: {fold_feats_path}")
    print(f"Model chosen: {model_chosen}")
    os.makedirs(results_path, exist_ok=True)

    df_features, y = process_data(features_path, outcome_path)

    input_stem = Path(features_path).stem
    stims=get_stims(input_stem)

    data_dict=split_features_by_stim(df_features, stims)
    if not data_dict:
        raise ValueError("No stim-specific features found. Please check your feature names.")

    # ---------------------------
    # Define cross-validation splits
    # ---------------------------
    groups = df_features.index.to_series().apply(lambda x: x.split('_')[0])

    outer_cv = GroupShuffleSplit(n_splits=100, test_size=0.2, random_state=42)

    print(f"INFO: Using GroupShuffleSplit for outer CV ({groups.nunique()} groups/folds expected).")

    estimators = get_estimators(artificial_type_arg)

    models = [
        "STABL ALasso",
        "STABL Lasso",
        "STABL ElasticNet",
    ]

    # Define parameters grid for XGBoost
    param_grid = {
        "n_estimators": [300, 500],
        "max_depth": [2, 4, 10],
        "learning_rate": [0.01, 0.05],
        "subsample": [0.5, 0.7],
        "colsample_bytree": [0.5,0.8],
        'gamma': [0,1], 
        'reg_alpha': [0], 
        'reg_lambda': [1]
    }

    all_combinations = list(itertools.product(*param_grid.values()))
    param_names = list(param_grid.keys())

    best_scores = {model: float("inf") for model in models}
    best_combinations = {model: None for model in models}
    best_paths = {model: None for model in models}

    for i, param_values in enumerate(all_combinations):
        param_dict = dict(zip(param_names, param_values))
        print(f"\n==== Grid Search Iteration {i+1}/{len(all_combinations)} ====")
        print("Trying parameters:", param_dict)

        xgboost_model = XGBRegressor(**param_dict, verbosity=0)
        estimators["xgboost"] = xgboost_model
        
        tmp_path = Path(results_path) / f"gridsearch_tmp_{i}"
        tmp_path.mkdir(parents=True, exist_ok=True)

        # Launch prediction for this set of parameter
        predictions_dict = cv_on_existing_feats(
            data_dict=data_dict,
            y=y,
            outer_splitter=outer_cv,
            estimators=estimators,
            task_type="regression",
            model_chosen=model_chosen,
            fold_feats_path=fold_feats_path,
            save_path=tmp_path,
            models=models,
            outer_groups=groups,       
            early_fusion=False,
            late_fusion=False,
            n_iter_lf=100000
            )
        keep_tmp = False
        for model in models:
            true_y = y.loc[predictions_dict[model].index]
            pred_y = predictions_dict[model]
            mae = mean_absolute_error(true_y, pred_y)
            print(f"{model} → MAE: {mae:.4f}")
            rmse = np.sqrt(mean_squared_error(true_y, pred_y))
            print(f"{model} → RMSE: {rmse:.4f}")
        
            if rmse < best_scores[model]:
                best_scores[model] = rmse
                best_combinations[model] = param_dict
                best_paths[model] = tmp_path
                keep_tmp = True
        
        if not keep_tmp:
            shutil.rmtree(tmp_path)

    print("\n===== Best RMSEs per model =====")
    for model in models:
        print(f"{model} → RMSE: {best_scores[model]:.4f}, Best Params: {best_combinations[model]}")

    for model in models:
        final_model_path = Path(results_path) / model.replace(" ", "_")
        if final_model_path.exists():
            shutil.rmtree(final_model_path)
        shutil.copytree(best_paths[model], final_model_path)
        print(f"→ Best results for {model} saved to {final_model_path}")

if __name__ == "__main__":
    main()