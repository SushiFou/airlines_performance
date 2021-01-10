import pandas as pd
import numpy as np
import os

from sklearn.base import is_classifier
from sklearn.utils import _safe_indexing
from sklearn.model_selection import TimeSeriesSplit

from rampwf.utils.importing import import_module_from_source ## a revoir 
from rampwf.workflows import SKLearnPipeline
from rampwf.score_types import BaseScoreType
from rampwf.prediction_types.base import BasePrediction
import rampwf as rw

## https://paris-saclay-cds.github.io/ramp-workflow/problem.html
DATA_HOME = ""
DATA_PATH = "data/"
batch_size = 2# a changer
#WINDOWS_SIZE = 12

##############################################
# 3 - Score class
##############################################

class MAE (BaseScoreType):
    is_lower_the_better = True
    minimum = 0.0
    maximum = float('inf')

    def __init__(self, name='rmse', precision=2):
        self.name = name
        self.precision = precision

    def __call__(self, y_true, y_pred):
        error = []
        y_true = pd.DataFrame(y_true, columns=['DATE','UNIQUE_CARRIER_NAME', 'LOAD_FACTOR'])
        y_pred = pd.DataFrame(y_pred, columns=['DATE','UNIQUE_CARRIER_NAME', 'LOAD_FACTOR'])
        carriers = np.unique( y_true['UNIQUE_CARRIER_NAME'])
        m_df = y_pred.merge(y_true,how = 'left', on = ['DATE', 'UNIQUE_CARRIER_NAME'])
        for carrier in carriers:
          if carrier != 'US Airways Inc.':
            y_true_c = m_df[m_df['UNIQUE_CARRIER_NAME'] == carrier]['LOAD_FACTOR_x']#y_true.get(carrier)
            y_pred_c = m_df[m_df['UNIQUE_CARRIER_NAME'] == carrier]['LOAD_FACTOR_y']##a changer
            error.extend(np.abs(y_true_c - y_pred_c) / len(y_true_c))
        return np.mean(error)
##############################################
# 3 - Workflow class
##############################################
class EstimatorAirlines(SKLearnPipeline):

    def __init__(self):
        super().__init__()
    def train_submission(self, module_path, X, y, train_idx=None):
        """Train the estimator of a given submission.
        Parameters
        ----------
        module_path : str
            The path to the submission where `filename` is located.
        X : {array-like, sparse matrix, dataframe} of shape \
                (n_samples, n_features)
            The data matrix.
        y : array-like of shape (n_samples,)
            The target vector.
        train_idx : array-like of shape (n_training_samples,), default=None
            The training indices. By default, the full dataset will be used
            to train the model. If an array is provided, `X` and `y` will be
            subsampled using these indices.
        Returns
        -------
        estimator : estimator object
            The scikit-learn fitted on (`X`, `y`).
        """
        train_idx = slice(None, None, None) if train_idx is None else train_idx
        submission_module = import_module_from_source(
            os.path.join(module_path, self.filename),
            os.path.splitext(self.filename)[0],  # keep the module name only
            sanitize=True
        )
        estimator = submission_module.get_estimator()
        X_train = _safe_indexing(X, train_idx)
        y_train = _safe_indexing(y, train_idx)
        ####
        y_train = pd.DataFrame(y_train, columns=['DATE','UNIQUE_CARRIER_NAME', 'LOAD_FACTOR'])
        estimators = {}
        carriers = np.unique( X_train['UNIQUE_CARRIER_NAME'])
        for carrier in carriers:
            if carrier != 'US Airways Inc.':
                X = X_train[X_train['UNIQUE_CARRIER_NAME'] == carrier]
                X.drop(columns='UNIQUE_CARRIER_NAME', inplace=True)
                Y = y_train[y_train['UNIQUE_CARRIER_NAME'] == carrier]
                estimators[carrier] = estimator.fit(X,Y)
        ####
        return estimators

    def test_submission(self, estimator_fitted, X):
        """Predict using a fitted estimator.
        Parameters
        ----------
        estimator_fitted : Estimator object
            A fitted scikit-learn estimator.
        X : {array-like, sparse matrix, dataframe} of shape \
                (n_samples, n_features)
            The test data set.
        Returns
        -------
        pred : ndarray of shape (n_samples, n_classes) or (n_samples)
        """
        ######
        carriers = np.unique( X['UNIQUE_CARRIER_NAME'])
        predictions = pd.DataFrame(columns= ['UNIQUE_CARRIER_NAME','PRED'])
        for carrier in carriers:
          if carrier != 'US Airways Inc.':
            X_used = X[X['UNIQUE_CARRIER_NAME'] == carrier]
            y_pred_sub=pd.DataFrame( X[X['UNIQUE_CARRIER_NAME'] == carrier]['UNIQUE_CARRIER_NAME'][batch_size:],columns= ['UNIQUE_CARRIER_NAME','PRED'])
            X_used.drop(columns='UNIQUE_CARRIER_NAME', inplace=True)
            predictions_tmp = estimator_fitted.get(carrier).predict(X_used)
            y_pred_sub['PRED'] = predictions_tmp
            predictions = predictions.append(y_pred_sub)
        predictions.reset_index(level=0, inplace=True)
        if predictions is None:
            raise ValueError('NaNs found in the predictions.')
        #########
        print(np.array(predictions))
        print('-----------------------------------')
        return np.array(predictions)
        
##############################################
# 3 - Prediction type class
##############################################
class _Predictions(BasePrediction):
    def __init__(self,n_columns, y_pred=None, y_true=None, n_samples=None,):
        """Essentially the same as in a regression task, but the prediction is a list not a float."""
        self.n_columns = n_columns
        if y_pred is not None:
            self.y_pred = y_pred 
        elif y_true is not None:
            self.y_true = y_true
        elif n_samples is not None:
            # self.n_columns == 0:
            shape = n_samples
            self.y_pred = df.dataframe()
            self.y_pred.fill(np.nan)
        else:
            raise ValueError(
                "Missing init argument: y_pred, y_true, or n_samples"
            )
        self.check_y_pred_dimensions()
        ## deja fait en base ##https://github.com/paris-saclay-cds/ramp-workflow/blob/master/rampwf/prediction_types/base.py

    @property
    def valid_indexes(self):
        """Return valid indices (e.g., a cross-validation slice)."""
        if len(self.y_pred.shape) == 2:
            return ~pd.isnull(self.y_pred[:, 0])
        else:
            raise ValueError("y_pred should be 2D (dataframe)")


def _regression_init(self, y_pred=None, y_true=None, n_samples=None):
    if y_pred is not None:
        self.y_pred = np.array(y_pred)
    elif y_true is not None:
        self.y_true = np.array(y_true)
    elif n_samples is not None:
        if self.n_columns == 0:
            shape = (n_samples)
        else:
            shape = (n_samples, self.n_columns)
        self.y_pred = np.empty(shape, dtype=float)
        self.y_pred.fill(np.nan)
    else:
        raise ValueError(
            'Missing init argument: y_pred, y_true, or n_samples')
    #self.check_y_pred_dimensions()


##############################################
#4 - definir functions
##############################################

def make_LF_detection(label_names=[]):
    #_Predictions(n_columns = 3)
    Predictions = type(
        'Regression',
        (BasePrediction,),
        {'label_names': label_names,
         'n_columns': len(label_names),
         'n_columns_true': len(label_names),
         '__init__': _regression_init,
         })
    return 
    
def make_workflow(): 
    ## a faire
    return EstimatorAirlines()

def get_cv(X, y):
    #https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
    tscv = TimeSeriesSplit(n_splits=2) ## a voir plus d'option et size 
    return tscv.split(X, y)

def _read_data(path, dir_name):
    DATA_HOME = path
    data = pd.read_csv(os.path.join(DATA_HOME,DATA_PATH,dir_name, 'features.csv'),index_col = 0)
    data['DATE'] = pd.to_datetime(data['DATE'])
    #data.set_index('DATE', inplace=True)#pas besion ds le batch
    y_array = data[['DATE','UNIQUE_CARRIER_NAME', 'LOAD_FACTOR']]#'DATE',
    #y_array.reset_index(level=0, inplace=True)#pas besion ds le batch
    y_array = np.array(y_array)
    X_df = data
    return X_df, y_array


def get_train_data(path="."):
    return _read_data(path, 'train')


def get_test_data(path="."):
    return _read_data(path, 'test')


# def get_data(trainOrtest, path="."):

#     X_df = pd.read_csv(trainOrtest + 'X.csv' )
#     y = pd.read_csv(trainOrtest + 'y.csv' )
#     return  X_df, y

##############################################
#5- Definir nos variable de base
##############################################
problem_title = 'US Airlines Performance'

Predictions = make_LF_detection(label_names=['DATE','UNIQUE_CARRIER_NAME', 'LOAD_FACTOR'])
#Predictions =rw.prediction_types.make_regression(label_names=['DATE','UNIQUE_CARRIER_NAME', 'LOAD_FACTOR'])
## a voir si mettre contraint entre 0 et 1 ??
#https://github.com/paris-saclay-cds/ramp-workflow/blob/master/rampwf/prediction_types/regression.py

workflow = make_workflow() 
##TimeSeriesFeatureExtractor()
###https://github.com/paris-saclay-cds/ramp-workflow/blob/master/rampwf/workflows/ts_feature_extractor.py

score_types = [
     MAE(name='MAE')
]
#rw.score_types.RMSE(name='MSE')
#https://github.com/paris-saclay-cds/ramp-workflow/blob/master/rampwf/score_types/rmse.py
