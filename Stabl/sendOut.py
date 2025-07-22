from stabl.single_omic import single_omic_simple, save_single_omic_results
from stabl.EMS import generateModel,read_json,write_json,unroll_parameters
from sklearn.model_selection import LeaveOneOut,LeaveOneGroupOut, RepeatedStratifiedKFold
from stabl.stabl import save_stabl_results
from stabl.sherlock import run_end
from pathlib import Path
import numpy as np
import pandas as pd
import argparse
import os 


frequencies= pd.read_csv(f"/home/users/jeinhaus/Perio/AnalysisPerio1/Data/PerioPhase1_frequencies_BL.csv",index_col=0)
frequencies.columns = [col + "_frequency" for col in frequencies.columns]
Pgingivalis = pd.read_csv(f"/home/users/jeinhaus/Perio/AnalysisPerio1/Data/PerioPhase1_functional_BL_Pgingivalis.csv",index_col=0)
Cocktail = pd.read_csv(f"/home/users/jeinhaus/Perio/AnalysisPerio1/Data/PerioPhase1_functional_BL_Cocktail.csv",index_col=0)
IFNa = pd.read_csv(f"/home/users/jeinhaus/Perio/AnalysisPerio1/Data/PerioPhase1_functional_BL_IFNa.csv",index_col=0)
TNFa = pd.read_csv(f"/home/users/jeinhaus/Perio/AnalysisPerio1/Data/PerioPhase1_functional_BL_TNFa.csv",index_col=0)
Unstim = pd.read_csv(f"/home/users/jeinhaus/Perio/AnalysisPerio1/Data/PerioPhase1_functional_BL_Unstim.csv",index_col=0)

df = pd.concat([Pgingivalis, Cocktail, IFNa, TNFa, Unstim, frequencies], axis=1)
df_outcome = pd.read_csv("/home/users/jeinhaus/Perio/AnalysisPerio1/Outcome/Perio1_outcome.csv", index_col=0)
y = df_outcome["Group"]
taskType = 'binary'

orderby = "ROC AUC" if taskType == "binary" else "R2"
keepTop = 5

paramFilePath = "./params.json"
savePathRoot = "./results"
os.makedirs(savePathRoot, exist_ok=True)

def experiment(paramSet: dict,idx: int,savePath: str):
    name = str(idx)

    outerSplitter = RepeatedStratifiedKFold(n_splits=5,n_repeats=100,
                    random_state=paramSet["cvSeed"])

    stim = paramSet["dataset"]
    ef = (stim == "EarlyFusion")
    if ef:
        data = df
    else:
        data = df[[e for e in df.columns if stim in e]]


    preprocessing,model = generateModel(paramSet)
    results = single_omic_simple(
        data,
        y,
        outerSplitter,
        model,
        paramSet["model"],
        preprocessing,
        taskType,
        ef = ef
    )
    save_single_omic_results(y,results,savePath,taskType)

    if "stabl" in paramSet["model"]:
        data_std = pd.DataFrame(
            data=preprocessing.fit_transform(data),
            index=data.index,
            columns=preprocessing.get_feature_names_out()
        )
        model.fit(data_std,y)
        modelPath = Path(savePath,name,"fullModel")
        os.makedirs(modelPath,exist_ok = True)
        save_stabl_results(model,modelPath,data,y,override=True)



def postProcess(paramFilePath: str):
    run_end(paramFilePath,df,y,taskType)

        




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", type=int, default=0)
    parser.add_argument("idx", type=int, default=0,nargs="?")
    parser.add_argument("intensity",type=str,default='l',nargs="?")
    args = parser.parse_args()
    if args.mode == 0:
        path = Path(savePathRoot,str(args.intensity),str(args.idx))
        experiment(read_json(Path(path,"params.json")),args.idx,path)
    elif args.mode == 1:
        postProcess(paramFilePath)
        
