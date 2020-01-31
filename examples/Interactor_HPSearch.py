# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import os

os.environ["CUDA_VISIBLE_DEVICES"] = "5"
import pandas as pd
import logging
import numpy as np

from autorecsys.searcher.core import hyperparameters as hp_module
# from autorecsys.searcher.core.hyperparameters import HyperParameters as hp_module
from autorecsys.auto_search import Search
from autorecsys.pipeline import Input, LatentFactorMapper, MLPInteraction, RatingPredictionOptimizer, \
    ElementwiseInteraction, ConcatenateInteraction

from autorecsys.utils.common import set_device
from autorecsys.pipeline.preprocessor import Movielens1MPreprocessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def mf_pipeline():
    # set GPU devices
    # set_device('cpu:0')

    # # load dataset
    ml_1m = Movielens1MPreprocessor("./tests/datasets/ml-1m/ratings.dat")
    ml_1m.preprocessing(test_size=0.1, random_state=1314)
    train_X, train_y, val_X, val_y = ml_1m.train_X, ml_1m.train_y, ml_1m.val_X, ml_1m.val_y

    # Build the pipeline.
    # input_node = StructuredDataInput(column_names=['user_id', 'item_id'])
    input_node = Input(shape=[2])
    # cpu_num should default to None.
    user_emb = LatentFactorMapper(feat_column_id=0,
                                  id_num=10000,
                                  embedding_dim=10)(input_node)
    item_emb = LatentFactorMapper(feat_column_id=1,
                                  id_num=10000,
                                  embedding_dim=10)(input_node)

    output1 = MLPInteraction()([user_emb, item_emb])
    output2 = MLPInteraction(units=256,
                             num_layers=3,
                             use_batchnorm=False,
                             dropout_rate=0.1
                             )([output1])
    output3 = MLPInteraction()([output1, output2])

    output4 = MLPInteraction(units=256)([output1, output2, output3])

    output5 = MLPInteraction(units=256)([output4])

    output6 = ElementwiseInteraction(elementwise_type="innerporduct")([output4, output5])

    output7 = ConcatenateInteraction()([output6, output4])

    output8 = ConcatenateInteraction()([output6, output4])

    output9 = ConcatenateInteraction()([output6, output4])

    output = ConcatenateInteraction()([output7, output8, output9])

    final_output = RatingPredictionOptimizer()(output)

    # AutoML search and predict.
    # cf_searcher = Search(tuner='random',
    #                      tuner_params={'max_trials': 3, 'overwrite': True},
    #                      inputs=input_node,
    #                      outputs=final_output)

    cf_searcher = Search(tuner='hyperband',
                         tuner_params={"max_trials": 20},
                         inputs=input_node,
                         outputs=final_output)

    cf_searcher.search(x=train_X, y=train_y, x_val=val_X, y_val=val_y, objective='val_mse', batch_size=1000)
    logger.info('Predicted Ratings: {}'.format(cf_searcher.predict(x=val_X)))
    logger.info('Predicting Accuracy (mse): {}'.format(cf_searcher.evaluate(x=val_X, y_true=val_y)))


if __name__ == "__main__":
    mf_pipeline()