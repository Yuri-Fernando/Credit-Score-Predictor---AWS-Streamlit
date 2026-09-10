import os
import pandas as pd
import xgboost as xgb
import joblib

if __name__ == '__main__':
    train_path = os.path.join('/opt/ml/input/data/train', 'train.csv')
    df = pd.read_csv(train_path)

    target = 'target'
    features = [c for c in df.columns if c != target]

    X = df[features].values
    y = df[target].values

    dtrain = xgb.DMatrix(X, label=y)

    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'eta': 0.1,
        'max_depth': 6
    }

    num_round = 100
    model = xgb.train(params, dtrain, num_round)

    model_path = '/opt/ml/model'
    os.makedirs(model_path, exist_ok=True)
    model.save_model(os.path.join(model_path, 'xgboost-model'))

    # salvar ordem das features para o inferência Lambda
    joblib.dump(features, os.path.join(model_path, 'features.joblib'))
