#!/usr/bin/env python
# coding: utf-8

## Importing Packeges
import pandas as pd
import numpy as np
import requests
import math
import sys
import graphviz 
import matplotlib.pyplot as plt

from scipy import stats
from sklearn.model_selection import train_test_split
from sklearn.model_selection import ParameterGrid 
from sklearn.preprocessing import MinMaxScaler

from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import MultinomialNB
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier,
GradientBoostingClassifier, AdaBoostClassifier, BaggingClassifier)


from sklearn.metrics import accuracy_score as accuracy, confusion_matrix, f1_score, auc, roc_auc_score, precision_score
from sklearn.metrics import roc_curve, precision_recall_curve

import os
import csv
import config
from aequitas.group import Group
from aequitas.plotting import Plot



## Get Data

def get_csv(f):
    '''
    Description: This function takes a csv file and uploads it into a pandas dataframe
    Input:
        csv: file to upload
    Output:
        pandas data frame
    '''

    df = pd.read_csv(f)
    return df

## Pre-ProcessData

def remove_outliers(df, attribute_lst, sd_threshold=3):
    '''
    Takes a dataframe and number of standard deviations to be considered
    as outlier and returns a df without the observation that have one or
    or more outliers in the attributes selected.
    input:
    df: pandas data frame
    attributes_lst: list of attributes names
    sd_threshold: standard deviations
    output:
    the new datafrane without outliers
    '''
    zscore = lambda x: (x - x.mean())/x.std(ddof=0)
    for attribute in attribute_lst:
        df[attribute] = df[attribute][(np.abs(zscore(df[attribute])) < sd_threshold)]
    return df

def na_fill_col(df, col, fill_method = np.mean):
    '''
    This function fills NA values in a df column by given method

    df: dataframe
    fill_method: function specifying how to fill the NA values
    col: column name

    return: None

    Used in main.py
    '''
    cp = df.copy()
    cp.loc[cp[col].isna(), col] = fill_method(cp[col])
    df[col] = cp[col]
    return df


def impute_with_2cols(df, year_col, pen_col, target_col):
    '''
    This function creates a missing binary column and imputes age using the 
    helper column values given year of crime and sentencing penalty class code

    df: dataframe
    year_col: colname with date of offense
    pen_col: colname with penalty class code info
    target_col: column to impute

    returns dataframe with imputed data
    Used in main.py
    '''
    # find mean age given year and penalty class
    def find_mean(year, pen_class):
        #print(year)
        #print(pen_class)
        tmp = df[(df[year_col] == year) & (df[pen_col] == pen_class)]
        #print(tmp)
        return np.mean(tmp[target_col])
    
    # create binary missing column 
    # df = create_indicator(df, target_col)

    # copy dataframe to impute values then reinsert into df
    cp = df.copy()
    cp[target_col]= cp.apply(lambda row: find_mean(row[year_col], row[pen_col]) if pd.isnull(row[target_col]) else row[target_col], axis=1)
    cp.loc[cp[target_col].isna(), target_col] = find_mean(cp[year_col], cp[pen_col])
    df[target_col] = cp[target_col]
    return df


def fill_nan(df, attributes_lst, how='mean'):
    '''
    Fills the nan with the "how" specified.
    input:
        df: pandas data frame
        attributes_lst: list of attributes names
        how: {mean, max, min or median} of that attribute in the sample
    output:
        dataframe with the replaced nan
    '''   
    if how == 'mean':
        for attribute in attributes_lst: 
            df[attribute].fillna(df[attribute].mean(), inplace=True)
    elif how == 'max':
        for attribute in attributes_lst: 
            df[attribute].fillna(df[attribute].max(), inplace=True)
    elif how == 'min':
        for attribute in attributes_lst: 
            df[attribute].fillna(df[attribute].min(), inplace=True)
    elif how == 'median':
        for attribute in attributes_lst: 
            df[attribute].fillna(df[attribute].median(), inplace=True)
    else:
        raise Exception("This function only allows to fill the Nan with\
                        the mean, max, min or median of the observations")

        
def to_int(df, attribute_lst):
    '''
    Converts the data type of a string to an integer if possible or another\
    type of numberic data if not.
    input:
        df: pandas data frame
        attributes_lst: list of attributes names
    output:
        a df with the corresponding numeric variables
    '''
    
    for var in attribute_lst:
        df[var] = pd.to_numeric(df[var], errors='coerce', downcast='integer') 
    return df

       

def to_date(df, attribute_lst, years_range=[1000, 3000]):
    '''
    Converts the data type of a string in the format YYYY-MM-DD to a datetime and\
    replace to None the dates that fall outsithe the range of years specified
    input:
        df: pandas data frame
        attributes_lst: list of attributes names
        year_range: a tupple or list where the first year if the lowest bound \
        and the second is the highest bound
    output:
        a df with the corresponding None
    '''
    
    #df = df.apply(out_of_range_to_none, axis=1, args=(years_range, attribute_lst))
    for var in attribute_lst:
        df[var] = df[var].astype('datetime64[s]')#, errors = 'ignore')
    return df


def out_of_range_to_none(row, year_range, attributes_lst): 
    '''
    Takes a row and a lists of columns and checks if the value falls out of the \
    intended range. When it does, it converts it to None.
    input:
        row: a series that represents a row
        year_range: a tupple or list where the first year is the lowest bound \
        and the second is the highest bound of the range. Both years are included,\
        i.e. the bounds are not converted to None.
        attributes_lst: list of attributes names
    output:
        a row with the corresponding None
    '''
    
    for col in attributes_lst:
        year = int(row[col].split("/")[2])
        if year < year_range[0] or year > year_range[1]:
            row[col] = None 
    return row


def impute_missing(df, col, fill_cat = 'MISSING'):
    '''
    This function creates a missing binary column and imputes fill_cat

    df: dataframe
    fill_cat: impute value

    returns dataframe with imputed data
    used in main.py
    '''
    # create binary missing column
    # df = pp.missing_col(df, col)
    # copy dataframe to impute values then reinsert into df
    cp = df.copy()
    cp.loc[cp[col].isna(), col] = fill_cat
    df[col] = cp[col]
    return df

## Generate Features/ Predictors


def discretize_variable(df, attribute_lst):
    '''
    Converts continuous variables into discrete variables
    input:
        df: pandas data frame
        attributes_lst: list of attributes names
    output:
        dataframe with the new variables
    ''' 

    for var in attribute_lst:
        new_var = var + 'cat'
        df[new_var] = pd.qcut(df[var], 10, duplicates="drop", labels=False)
    return df

def categorical_to_dummy(df, attribute_lst):
    '''
    Converts categorical variables into one variabel dummies for each category. 
    input:
        df: pandas data frame
        attributes_lst: list of attributes names
    output:
        dataframe with the new variables
    ''' 

    for var in attribute_lst:
        tmp = df[var]
        df = pd.get_dummies(df, columns=[var], dummy_na=False)
        df.loc[:,var] = tmp
    return df

def categorical_to_dummy_with_groupconcat(df, attribute_lst):
    for var in attribute_lst:
        dummy = df[var].str.get_dummies(sep=',')
        for d in dummy.columns:
            col_name = "{}_{}".format(var, d)
            df[col_name] = dummy[d]
    return df 

def flag_to_dummy(df, attribute_lst, rename=True):
    '''
    Converts a flag variable to a dummy with 1 for Yes and 0 for No
    '''
    for var in attribute_lst:
        df[var] = df[var].map({'Y': 1, 'N': 0, 'Yes': 1, 'No': 0, 'T': 1, 'F': 0, 't': 1, 'f': 0,
                                     'True': 1, 'False': 0, True: 1, False: 0, 'OPEN': 1, 'CLOSED': 0})
        if rename:
            new_var_name = var[:-5]
            df.rename(index=str, columns={var: new_var_name}, inplace=True)
    return df

def gender_to_dummy(df, gender_var):  
    '''
    Converts a gender indicative variable to a dummy with 1 for female and 0 for male
    '''
    df[gender_var] = df[gender_var].map({'FEMALE': 1, 'MALE': 0, 'F': 1, 'M': 0})
    df.rename(index=str, columns={gender_var: "FEMALE"}, inplace=True)
    return df

def create_indicator(df, col, indicator_name='missing'):
    '''
    This function creates binary column with missing or not
    
    df: dataframe
    fill_method: function specifying how to fill the NA values
    col: column name

    return: None
    '''
    missingcol = col + '_' + indicator_name
    df[missingcol] = [1 if x else 0 for x in df[col].isna()]
    return df


### Evaluation Metrics

def plot_scores_hist(df,col_score, model_name, output_type = 'save'):
    '''
    This function plots histogram of scores.

    df: dataframe
    col_score: column with scores
    model_name: name of model
    output_type: 'save', 'show', ''
    '''
    plt.clf()
    df[col_score].hist()
    plt.title(model_name)
    if output_type == 'save':
        f = os.path.join(config.GRAPH_FOLDER, model_name)
        plt.savefig(f)
    elif output_type == 'show':
        plt.show()


def plot_precision_recall_n(y_true, y_prob, model_name, subtitle, output_type):
    '''
    Plot precision and recall for each threshold

    Inputs:
        y_true: real labels for testing set
        y_prob: array of predicted scores from model
        model_name: (str) title for plot
        subtitle: subtitle
        output_type: (str) save or show
    '''
    plt.clf()
    y_score = y_prob
    precision_curve, recall_curve, pr_thresholds = precision_recall_curve(y_true, y_score)
    precision_curve = precision_curve[:-1]
    recall_curve = recall_curve[:-1]

    pct_above_per_thresh = []
    number_scored = len(y_score)
    for value in pr_thresholds:
        num_above_thresh = len(y_score[y_score>=value])
        pct_above_thresh = num_above_thresh / float(number_scored)
        pct_above_per_thresh.append(pct_above_thresh)

    pct_above_per_thresh = np.array(pct_above_per_thresh)
    
    fig, ax1 = plt.subplots()
    ax1.plot(pct_above_per_thresh, precision_curve, 'b')
    ax1.set_xlabel('percent of population')
    ax1.set_ylabel('precision', color='b')
    ax2 = ax1.twinx()
    ax2.plot(pct_above_per_thresh, recall_curve, 'orange')
    ax2.set_ylabel('recall', color='orange')
    ax1.set_ylim([0,1])
    ax1.set_ylim([0,1])
    ax2.set_xlim([0,1])
    ax1.axvline(x=0.2, ymin=0, ymax=1, color = 'gray')

    plt.suptitle(model_name)
    plt.title(subtitle)

    if (output_type == 'save'):
        pltfile = os.path.join(config.GRAPH_FOLDER,model_name)
        plt.savefig(pltfile)
    elif (output_type == 'show'):
        plt.show()
    else:
        pass

    
def f1_at_threshold(y_true, y_predicted):
    '''
    This function calculates the evaluation metric F! for a certain level 
    of possitive labeled observations. 
    Input:
        y_true: np.array with the observed Ys 
        y_predicted: np.array with the predicted Ys 
    Output:
        The F1 score
    '''
    return  f1_score(y_true, y_predicted)


def accuracy_at_threshold(y_true, y_predicted):
    '''
    This function calculates the evaluation metric called "accuracy" for a 
    certain level of possitive labeled observations. 
    Input:
        y_true: np.array with the observed Ys 
        y_predicted: np.array with the predicted Ys
    Output:
        The Accuracy score
    '''
    tn, fp, fn, tp = confusion_matrix(y_true, y_predicted).ravel()
    return 1.0 * (tp + tn) / (tn + fp + fn + tp )

def recall_at_threshold(y_true, y_predicted):
    '''
    This function calculates the evaluation metric called "recall" for a 
    certain level of possitive labeled observations. 
    Input:
        y_true: np.array with the observed Ys 
        y_predicted: np.array with the predicted Ys
    Output:
        The Recall score
    '''
    _, _, fn, tp = confusion_matrix(y_true, y_predicted).ravel()
    return 1.0 * tp / (tp + fn)

def precision_at_threshold(y_true, y_predicted):
    '''
    This function calculates the evaluation metric called "precision" for a 
    certain level of possitive labeled observations. 
    Input:
        y_true: np.array with the observed Ys 
        y_predicted: np.array with the predicted Ys
    Output:
        The Precision score
    '''
    
    _, fp, _, tp = confusion_matrix(y_true, y_predicted).ravel()
    return 1.0 * tp / (tp + fp)

def scores_pctpop(pred_scores, pct_pop):
    
    #identify number of positives to have given target percent of population
    num_pos = int(round(len(pred_scores)*(pct_pop/100),0))
    #turn predictions into series
    tmp = pred_scores.copy()
    pred_df = pd.Series(tmp)
    idx = pred_df.sort_values(ascending=False)[0:num_pos].index 
    
    #set all observations to 0
    pred_df.iloc[:] = 0
    #set observations by index (the ones ranked high enough) to 1
    pred_df.iloc[idx] = 1
    
    return list(pred_df)

def pred_at_level(y_true, y_scores, level):
    '''
    This function takes the predicted score and converts it into label 1 or 0
    based on the level -percentage of observations- decided to include, e.i. label 1. 
    Input:
        y_true: np.array with the observed Ys 
        y_scores: np.array with the predicted scores 
        level: percentage of the population labeled 1
    Output:
        The predicted label {0, 1}
    '''
    
    idx = np.argsort(np.array(y_scores))[::-1]
    y_scores, y_true = np.array(y_scores)[idx], np.array(y_true)[idx]
    cutoff_index = int(len(y_scores) * (level / 100.0))
    y_preds_at_level = [1 if x < cutoff_index else 0 for x in range(len(y_scores))]
    return y_true, y_preds_at_level


metrics = { 'accuracy':accuracy_at_threshold,
            'precision':precision_at_threshold,
            'recall':recall_at_threshold,
            'f1':f1_at_threshold,
            'auc':roc_auc_score}


# Understanding Best models #

def get_best_models(df, time_col, test_years, cols, metric):
    '''
    Identify best models for the specified metric
    Inputs:
        df: pandas dataframe of results
        time_col: (str) name of the col that identifies different traintest sets 
        test_years: list of years in results
        cols: list of cols for the table
        metric: (str) precision, recall, accuracy, f1_score, auc
    
    Return dataframe of best model for the specified metric
    '''
    best_models = pd.DataFrame(columns= cols)

    for year in test_years:
        year_data = df[df[time_col]==year]
        highest = year_data[metric].max()
        model = year_data[year_data[metric] == highest]
        print("For train-test set {}, highest {} attained is {}".format(year, metric, highest))
        best_models = best_models.append(model[cols])

    return best_models

def sort_models(data, metric, top_k, cols):
    '''
    Get top k models
    '''
    sort = data.sort_values(metric, ascending=False)
    results = sort[cols][:top_k]
    return results


def get_stability_score(trainsets, metric, cols):
    '''
    Identify models that are top ranking in all train test sets
    Inputs:
        trainsets: list of dataframes that correspond to each traintest set
    '''
    result = pd.DataFrame()
    for sets in trainsets:
        sort = sets.sort_values(metric, ascending=False)
        sort['rank'] = range(len(sort))
        result = result.append(sort)
    result = result[cols + ['rank']]
    return result.groupby('parameters').mean().sort_values('rank')


def get_metric_graph(df, metric, model_and_para, baseline, train_test_col, 
                     train_test_val, title, filename):
    '''
    Inputs:
        df: pandas dataframe of results
        metric: str e.g. 'precision_at_5'
        model_and_para: list of tuples containing models and paras in str 
            e.g. [('model', 'parameters'), ('model','parameters')]
        train_test_col: column name for train test sets (str)
        train_test_val: list of values in train test sets
        baseline: list of baselines over the train test sets
        title: title of graph
    '''
    def get_data(df, dic, model, para, metric, train_test_col, train_test_val):
        '''
        Getting the data points to plot
        '''
        col = []
        for yr in train_test_val:
            trainset = df[df[train_test_col]==yr]
            temp = trainset[trainset['parameters']==para][[metric]]
            col.extend(temp[metric].values)
        dic[model + ' ' + para] = col
        return dic
    
    def plot_graph(df, metric, title, filename, save=False):
        '''
        Plot metric over different traintest sets
        '''
        df.plot.line()
        plt.title(title)
        plt.ylabel(metric)
        plt.xticks([0,1,2], ['jul12','jan12','jul13'])
        if metric.startswith('precision'):
            plt.yticks([0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0])
        else:
            plt.yticks([0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0])
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), shadow=True, ncol=1)
        if save:
            plt.savefig(filename)
        plt.show()

    full_dict = {}

    for m in model_and_para:
        model, para = m
        full_dict = get_data(df, full_dict, model, para, metric, 
                             train_test_col, train_test_val)
    new_df = pd.DataFrame(full_dict)
    
    plot_graph(new_df, metric, title, filename, save=True)


### Master Classifier

classifiers = { 'RF': RandomForestClassifier(n_jobs=-1, random_state=config.SEED),
                'ET': ExtraTreesClassifier(n_jobs=-1, criterion='entropy', random_state=config.SEED),
                'AB': AdaBoostClassifier(DecisionTreeClassifier(max_depth=1), random_state=config.SEED),
                'GB': GradientBoostingClassifier(learning_rate=0.05, subsample=0.5, max_depth=6,
                                                n_estimators=10, random_state=config.SEED),
                'KNN': KNeighborsClassifier(n_neighbors=3),
                'DT': DecisionTreeClassifier(max_depth=5, random_state=config.SEED),
                'SVM': LinearSVC(random_state=config.SEED),
                'LR': LogisticRegression(penalty='l1', C=1e5, random_state=config.SEED),
                'BAG': BaggingClassifier(random_state=config.SEED),
                'NB': MultinomialNB(alpha=1.0)
        }

def plot_bias(model_name, bias_df, bias_metrics = ['ppr','pprev','fnr','fpr', 'for'], min_group_size = None, output_type = None):
    '''
    This function creates bar charts for bias metrics given.

    bias_df = dataframe with ID, label, predicted scores already taking into account the population threshold, and 
    '''
    g = Group()
    xtab, _ = g.get_crosstabs(bias_df)
    aqp = Plot()
    n = len(bias_metrics)
    p = aqp.plot_group_metric_all(xtab, metrics=bias_metrics, ncols=n, min_group_size = min_group_size)
    if output_type == 'save':
        pltfile = os.path.join(config.GRAPH_FOLDER,model_name)
        p.savefig(pltfile)
    elif output_type == 'show':
        p.show()
    return

def classify(train_set, test_set, label, models, eval_metrics, eval_metrics_by_level, custom_grid, attributes_lst, bias_lst, bias_dict, year,
    results_dir, results_file, plot_pr = None, compute_bias =False, save_pred=False):
    '''
    This function fits a set of classifiers and a dataframe with performance measures for each
    Input:
        train_set, test_set: dataframe for training and testing the models
        label: name of the Y variable
        models: classifier models to fit
        eval_metrics: list of threshold-independent metrics.
        eval_metrics_by_level: tuple containing a list of threshold-dependent metrics as first element and a list of thresholds as second element
        custom_grid: grid of parameters
        attributes_lst: list containing the names of the features (i.e. X variables) to be used.
        bias_lst: list of column names for bias 
        bias_dict: dictionary of metrics for bias computation
        year: year of data, for saving files
        plot_pr: 'save', 'show', or None
        compute_bias: boolean whether or not to compute bias for each model
        save_pred: boolean whether to save final predictions
    Output:
        Dataframe containing performance measures for each classifier
    '''
    #initialize results
    results_columns = (['year','model','classifiers', 'parameters', 'train_set_size', 'num_features', 'validation_set_size', 'baseline'] + eval_metrics + 
                      [metric + '_' + str(level) for level in eval_metrics_by_level[1] for metric in eval_metrics_by_level[0]])
    
    # Write header for the csv
    outfile = os.path.join(results_dir, "{}_{}.csv".format(results_file, year))
    with open(outfile, "w") as f:
        csvwriter = csv.writer(f, delimiter=',')
        csvwriter.writerow(results_columns)

    # subset training and test sets 
    X_train = train_set.loc[:, attributes_lst]
    y_train = train_set[label]
    X_test = test_set.loc[:, attributes_lst]
    y_test = test_set[label]
    n_target = sum(test_set[label])
    n_observations = len(test_set[label])
    baseline = n_target/n_observations
    #print(sum(test_set[label]))
    #print(len(test_set[label]))
        
    features_txt = os.path.join(results_dir, "features_{}.txt".format(year))
    if not os.path.exists(features_txt):
        with open(features_txt, "w") as f:
            print(attributes_lst, file=f)

    # iterate through models
    for model in models:
        #create parameters grids
        grid = ParameterGrid(custom_grid[model])
        # iterate through parameters for given model
        for parameters in grid:
            classifier = classifiers[model]
            print('Running model: {}, param: {}'.format(model, parameters))
            # set parameters
            clfr = classifier.set_params(**parameters)
            # fit model
            clfr.fit(X_train, y_train)
            
            # add baseline for test set
            eval_result = [year, model, classifier, parameters, len(X_train), len(attributes_lst), len(X_test), baseline]

            # calculate scores
            if isinstance(clfr, LinearSVC):
                y_pred_prob = clfr.decision_function(X_test)
            else:    
                y_pred_prob = clfr.predict_proba(X_test)[:,1]

            # add score to data
            test_set['SCORE'] = y_pred_prob
            # plot and save score distributions
            model_name = 'HIST_{}_{}_{}.png'.format(year, model, str(parameters).replace(':','-'))
            plot_scores_hist(test_set, 'SCORE', model_name, output_type = 'save')

            # Calculate final label
            test_set['PREDICTION'] = scores_pctpop(y_pred_prob, config.POP_THRESHOLD)
            #print(y_pred_prob)
            # save final predictions to file
            if save_pred:
                filename = 'PRED_{}_{}_{}.csv'.format(year, model, str(parameters).replace(':','-'))
                f = os.path.join(config.RESULTS_DIR,filename)
                final_pred = test_set.loc[:, ['ID', 'PREFIX', 'START_DATE', 'END_DATE', 'LABEL', 'SCORE','PREDICTION']]
                final_pred.to_csv(f, index=False)
            
            # plot precision and recall if desired
            if plot_pr:
                model_name = 'PRC_{}_{}_{}.png'.format(year, model, str(parameters).replace(':','-'))
                print('plotting precision recall for {}'.format(model_name))
                rec = recall_at_threshold(y_test, test_set['PREDICTION'])
                subtitle = 'Recall at {} is {}'.format(config.POP_THRESHOLD, rec)
                plot_precision_recall_n(y_test, y_pred_prob, model_name, subtitle, plot_pr)

            # plot bias metrics if desired
            if compute_bias:
                # reconfigure test set to have the correct column names
                tmp = test_set.copy()
                tmp['id'] = tmp['ID']
                tmp['score'] = tmp['PREDICTION']
                tmp['label_value'] = tmp[label]
                bias_df = tmp.loc[:, bias_lst]
                # plot and save bias
                model_name = 'BIAS_{}_{}_{}.png'.format(year, model, str(parameters).replace(':','-'))
                plot_bias(model_name, bias_df, bias_metrics = bias_dict['metrics'], 
                    min_group_size = bias_dict['min_group_size'], output_type = 'save')

            # evaluate metrics
            if eval_metrics:
                eval_result += [metrics[metric](y_test, y_pred_prob) for metric in eval_metrics]
            
            if eval_metrics_by_level[0]:
                for level in eval_metrics_by_level[1]:
                   y_pred = scores_pctpop(y_pred_prob, level)
                   eval_result += [metrics[metric](y_test, y_pred) for metric in eval_metrics_by_level[0]]
            
            # writing out results in csv file
                with open(outfile, "a") as f:
                    csvwriter = csv.writer(f)
                    csvwriter.writerow(eval_result)
            
            # results.loc[len(results)] = eval_result

            # if model == models[0]:
            #     results.to_csv(outfile, index=False)
            # else:
            #     with open(os.path.join(results_dir, "{}_{}.csv".format(results_file, year)), 'a') as f:
            #         results.to_csv(f, header=False, index=False) 
    #return results
