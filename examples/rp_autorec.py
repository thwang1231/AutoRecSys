# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "2"

import logging
from autorecsys.auto_search import Search
from autorecsys.pipeline import Input, LatentFactorMapper, RatingPredictionOptimizer, HyperInteraction
from autorecsys.pipeline.preprocessor import MovielensPreprocessor

# logging setting
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load dataset
ml_1m = MovielensPreprocessor("./examples/datasets/ml-1m/ratings.dat")
ml_1m.preprocessing(test_size=0.1, random_state=1314)
train_X, train_y, val_X, val_y = ml_1m.train_X, ml_1m.train_y, ml_1m.val_X, ml_1m.val_y

# build the pipeline.
input = Input(shape=[2])
user_emb = LatentFactorMapper(feat_column_id=0,
                              id_num=10001,
                              embedding_dim=10)(input)
item_emb = LatentFactorMapper(feat_column_id=1,
                              id_num=10001,
                              embedding_dim=10)(input)
output1 = HyperInteraction()([user_emb, item_emb])
output2 = HyperInteraction()([output1, user_emb, item_emb])
output3 = HyperInteraction()([output1, output2, user_emb, item_emb])
output4 = HyperInteraction()([output1, output2, output3, user_emb, item_emb])
output = RatingPredictionOptimizer()(output4)

# AutoML search and predict.
cf_searcher = Search(tuner='random', ## hyperband, bayesian
                     tuner_params={'max_trials': 100, 'overwrite': True},
                     inputs=input,
                     outputs=output)
cf_searcher.search(x=train_X,
                   y=train_y,
                   x_val=val_X,
                   y_val=val_y,
                   objective='val_mse',
                   batch_size=256)
logger.info('Predicted Ratings: {}'.format(cf_searcher.predict(x=val_X)))
logger.info('Predicting Accuracy (mse): {}'.format(cf_searcher.evaluate(x=val_X, y_true=val_y)))