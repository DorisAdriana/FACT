from ..utils import *
import numpy as np
import json

class Dataset():
    def __init__(self, preprocessing_args):
        super().__init__()
        self.args = preprocessing_args

        self.sentiment_data = None
        self.user_name_dict = {}  # rename users to integer names
        self.item_name_dict = {}
        self.feature_name_dict = {}
        self.G0 = None
        self.G1 = None

        self.features = []  # feature list
        self.users = []
        self.items = []

        # the interacted items for each user, sorted with date {user:[i1, i2, i3, ...], user:[i1, i2, i3, ...]}
        self.user_hist_inter_dict = {}
        # the interacted users for each item
        self.item_hist_inter_dict = {} 

        self.user_num = None
        self.item_num = None
        self.feature_num = None  # number of features

        self.user_feature_matrix = None  # user aspect attention matrix
        self.item_feature_matrix = None  # item aspect quality matrix

        self.training_data = None
        self.test_data = None

        self.pre_processing()
        self.get_user_item_feature_matrix() # Get the attention matrices
        self.sample_training()  # sample training data, for traning BPR loss
        self.sample_test()  # sample test data

    def pre_processing(self,):
        sentiment_data = []

        #load data
        with open(self.args.sentires_dir, 'r') as f:
            line = f.readline().strip()
            while line:
                splitline = line.split('@')
                user = splitline[0]
                item = splitline[1]
                sentiment_data.append([user, item])
                fosr_data = splitline[3]
                for seg in fosr_data.split('||'):
                    fos = seg.split(':')[0].strip('|')
                    if len(fos.split('|')) > 1:
                        feature = fos.split('|')[0]
                        opinion = fos.split('|')[1]
                        sentiment = fos.split('|')[2]
                        sentiment_data[-1].append([feature, opinion, sentiment])
                line = f.readline().strip()
        sentiment_data = np.array(sentiment_data, dtype="object")
        if self.args.extra_filter: # extra filtering for computational reasons
            sentiment_data = sentiment_data_filtering(sentiment_data, self.args.item_thresh, self.args.user_thresh)
        user_dict, item_dict = get_user_item_dict(sentiment_data)
        user_item_date_dict = {}

        # remove duplicates [could be optimized]
        for i, line in enumerate(open(self.args.review_dir, "r")):
            record = json.loads(line)
            user = record['reviewerID']
            item = record['asin']
            date = record['unixReviewTime']
            if user in user_dict and item in user_dict[user] and (user, item) not in user_item_date_dict:
                user_item_date_dict[(user, item)] = date

        user_name_dict = {}
        item_name_dict = {}
        feature_name_dict = {}
        features = get_feature_list(sentiment_data)

        # Rename identifications to ints
        count = 0
        for user in user_dict:
            if user not in user_name_dict:
                user_name_dict[user] = count
                count += 1
        count = 0
        for item in item_dict:
            if item not in item_name_dict:
                item_name_dict[item] = count
                count += 1
        count = 0
        for feature in features:
            if feature not in feature_name_dict:
                feature_name_dict[feature] = count
                count += 1

        for i in range(len(sentiment_data)):
            sentiment_data[i][0] = user_name_dict[sentiment_data[i][0]]
            sentiment_data[i][1] = item_name_dict[sentiment_data[i][1]]
            for j in range(len(sentiment_data[i]) - 2):
                sentiment_data[i][j+2][0] = feature_name_dict[sentiment_data[i][j + 2][0]]

        renamed_user_item_date_dict = {}
        for key, value in user_item_date_dict.items():
            renamed_user_item_date_dict[user_name_dict[key[0]], item_name_dict[key[1]]] = value
        user_item_date_dict = renamed_user_item_date_dict

        # sort with date
        user_item_date_dict = dict(sorted(user_item_date_dict.items(), key=lambda item: item[1]))

        # NOT SURE WHAT THIS LAST PART DOES YET
        user_hist_inter_dict = {}  # {"u1": [i1, i2, i3, ...], "u2": [i1, i2, i3, ...]}, sort with time
        item_hist_inter_dict = {}
        # ranked_user_item_dict = {}  # {"u1": [i1, i2, i3, ...], "u2": [i1, i2, i3, ...]}
        for key, value in user_item_date_dict.items():
            user = key[0]
            item = key[1]
            if user not in user_hist_inter_dict:
                user_hist_inter_dict[user] = [item]
            else:
                user_hist_inter_dict[user].append(item)
            if item not in item_hist_inter_dict:
                item_hist_inter_dict[item] = [user]
            else:
                item_hist_inter_dict[item].append(user)

        user_hist_inter_dict = dict(sorted(user_hist_inter_dict.items()))
        item_hist_inter_dict = dict(sorted(item_hist_inter_dict.items()))

        users = list(user_hist_inter_dict.keys())
        items = list(item_hist_inter_dict.keys())

        self.G0 = split_groups(sentiment_data)[0] #Group(sentiment_data, long_tail=False) 
        self.G1 = split_groups(sentiment_data)[1] #Group(sentiment_data, long_tail=True) #has to be the very last step for the indices to match
        self.sentiment_data = sentiment_data
        self.user_name_dict = user_name_dict
        self.item_name_dict = item_name_dict
        self.feature_name_dict = feature_name_dict
        self.user_hist_inter_dict = user_hist_inter_dict # WHERE ARE THESE USED?
        self.item_hist_inter_dict = item_hist_inter_dict #
        self.users = users
        self.items = items
        self.features = features
        self.user_num = len(users)
        self.item_num = len(items)
        self.feature_num = len(features)
        return True
    
    def get_user_item_feature_matrix(self):
        # exclude test data from the sentiment data to construct matrix
        train_u_i_set = set()
        for user, items in self.user_hist_inter_dict.items():
            items = items[:-self.args.test_length]
            for item in items:
                train_u_i_set.add((user, item))

        train_sentiment_data = []
        for row in self.sentiment_data:
            user = row[0]
            item = row[1]
            if (user, item) in train_u_i_set:
                train_sentiment_data.append(row)
        self.user_feature_matrix = get_user_attention_matrix(
            train_sentiment_data, 
            self.user_num, 
            self.features, 
            max_range=5)
        self.item_feature_matrix = get_item_quality_matrix(
            train_sentiment_data, 
            self.item_num, 
            self.features, 
            max_range=5)
        return True
    
    def sample_training(self):
        print('======================= sample training data =======================')
        # print(self.user_feature_matrix.shape, self.item_feature_matrix.shape)
        training_data = []
        item_set = set(self.items)
        for user, items in self.user_hist_inter_dict.items():
            items = items[:-(self.args.test_length)]
            training_pairs = sample_training_pairs(
                user, 
                items, 
                item_set, 
                self.args.sample_ratio)
            for pair in training_pairs:
                training_data.append(pair)
        print('# training samples :', len(training_data))
        self.training_data = np.array(training_data, dtype="object")
        return True
    
    def sample_test(self):
        print('======================= sample test data =======================')
        user_item_label_list = []  # [[u, [item1, item2, ...], [l1, l2, ...]], ...]
        for user, items in self.user_hist_inter_dict.items():
            items = items[-(self.args.test_length):]
            user_item_label_list.append([user, items, np.ones(len(items))])  # add the test items
            negative_items = [item for item in self.items if 
                item not in self.user_hist_inter_dict[user]]  # the not interacted items
            negative_items = np.random.choice(np.array(negative_items), self.args.neg_length, replace=False)
            user_item_label_list[-1][1] = np.concatenate((user_item_label_list[-1][1], negative_items), axis=0)
            user_item_label_list[-1][2] = np.concatenate((user_item_label_list[-1][2], np.zeros(self.args.neg_length)), axis=0)
        print('# test samples :', len(user_item_label_list))
        self.test_data = np.array(user_item_label_list, dtype="object")
        return True
    
    def remove_features(self, index_list, method="both"):
        """
        Removes features from both user and item matrices by setting all values to zero.
        """
        for feature in index_list:
            if method != "item":
                self.user_feature_matrix[:, feature] = 0
            if method != "user":
                self.item_feature_matrix[:, feature] = 0
        return True

def preprocessing(preprocessing_args):
    rec_dataset = Dataset(preprocessing_args)
    return rec_dataset