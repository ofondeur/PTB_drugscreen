#!/usr/bin/env python
"""
Script to run STABL with ElasticNet/Lasso/ALasso (and the corresponding grid-search
baseline) on onset of labor data using late fusion by stim.
It loads the features from:
  ./Data/ina_13OG_final_long_allstims_filtered.csv
and the outcome (DOS, regression target) from:
  ./Data/outcome_table_all_pre.csv

It splits the features into separate data frames based on the stim suffix
(i.e. ifna, il246, unstim, lps, gmcsf), then runs multi‐omicTraceback (most recent call last)
Results (including scores, plots and selected features) are saved to:
  ./Results
"""

import os
import sys
from stabl_utils import get_estimators,split_features_by_stim,get_stims, process_data
sys.path.insert(0, '../Stabl')
from pathlib import Path
import numpy as np
import pandas as pd
import argparse

from sklearn.model_selection import GroupShuffleSplit
from stabl.multi_omic_pipelines import multi_omic_stabl_cv
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor


def main():
    parser = argparse.ArgumentParser(description="Run STABL Regression CV with configurable inputs.")
    parser.add_argument(
        "--features_path",
        required=True,
        help="Path to the input features CSV file (wide format)."
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

    # --- Use Parsed Arguments ---
    features_path = args.features_path
    artificial_type_arg = args.artificial_type
    model_chosen=args.model_chosen
    outcome_path = "../Data/outcome_table_all_pre.csv"

    input_stem = Path(features_path).stem 
    results_path=args.results_dir
    print(f"Input Features: {features_path}")
    print(f"Results will be saved to: {results_path}")
    print(f"Using STABL artificial type: {artificial_type_arg}")
    print(f"Model chosen: {model_chosen}")
    os.makedirs(results_path, exist_ok=True)

    df_features, y = process_data(features_path, outcome_path)

    stims=get_stims(input_stem)

    data_dict=split_features_by_stim(df_features, stims)
    if not data_dict:
        raise ValueError("No stim-specific features found. Please check your feature names.")
    groups = df_features.index.to_series().apply(lambda x: x.split('_')[0])
    outer_cv = GroupShuffleSplit(n_splits=100, test_size=0.2, random_state=42)

    print(f"INFO: Using GroupShuffleSplit for outer CV ({groups.nunique()} groups/folds expected).") # Optional: Add print statement

    estimators = get_estimators(artificial_type_arg)

    models = [
        "STABL Lasso",
        "STABL ALasso",
        "STABL ElasticNet",
    ]

    print("Starting multi-omic STABL CV with late fusion...")
    predictions_dict = multi_omic_stabl_cv(
        data_dict=data_dict,
        y=y,
        outer_splitter=outer_cv,
        estimators=estimators,
        task_type="regression",
        model_chosen=model_chosen,
        save_path=results_path,
        models=models,
        outer_groups=groups,       
        early_fusion=False, 
        late_fusion=False,
        n_iter_lf=100000
    )

    print("STABL CV finished.")
    print("Results (including r2, r, rmse, selected features, and plots) have been saved to:")
    print(results_path)

if __name__ == "__main__":
    main()