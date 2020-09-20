# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "2"

import logging
import tensorflow as tf
from autorecsys.auto_search import Search
from autorecsys.pipeline import Input, LatentFactorMapper, RatingPredictionOptimizer, HyperInteraction
from autorecsys.pipeline.preprocessor import MovielensPreprocessor
from autorecsys.recommender import RPRecommender

# logging setting
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# load dataset
##Netflix Dataset
# dataset_paths = ["./examples/datasets/netflix-prize-data/combined_data_" + str(i) + ".txt" for i in range(1, 5)]
# data = NetflixPrizePreprocessor(dataset_paths)

#Movielens 1M Dataset
movielens = MovielensPreprocessor()
train_X, train_y, val_X, val_y, test_X, test_y = movielens.preprocess()

user_num, item_num = movielens.get_hash_size()


# build the pipeline.
input = Input(shape=[2])
user_emb = LatentFactorMapper(feat_column_id=0,
                              id_num=user_num,
                              embedding_dim=64)(input)
item_emb = LatentFactorMapper(feat_column_id=1,
                              id_num=item_num,
                              embedding_dim=64)(input)
output1 = HyperInteraction()([user_emb, item_emb])
output2 = HyperInteraction()([output1, user_emb, item_emb])
output3 = HyperInteraction()([output1, output2, user_emb, item_emb])
output4 = HyperInteraction()([output1, output2, output3, user_emb, item_emb])
output = RatingPredictionOptimizer()(output4)
model = RPRecommender(inputs=input, outputs=output)

# AutoML search and predict.
searcher = Search(model=model,
                  tuner='random',  ## hyperband, bayesian
                  tuner_params={'max_trials': 2, 'overwrite': True},)
searcher.search(x=[movielens.get_x_categorical(train_X)],
                y=train_y,
                x_val=[movielens.get_x_categorical(val_X)],
                y_val=val_y,
                objective='val_mse',
                batch_size=1024,
                epochs=1,
                callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=1)])
logger.info('Predicting Val Dataset Accuracy (mse): {}'.format(searcher.evaluate(x=movielens.get_x_categorical(val_X), y_true=val_y)))
logger.info('Predicting Test Dataset Accuracy (mse): {}'.format(searcher.evaluate(x=movielens.get_x_categorical(test_X), y_true=test_y)))
