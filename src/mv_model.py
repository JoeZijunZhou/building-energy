import os
import datetime
from datetime import timedelta


import matplotlib
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm
from matplotlib import style

import numpy as np

import pandas as pd
from pandas.tseries.offsets import MonthEnd

from sklearn import svm, cross_validation, linear_model, preprocessing, ensemble
from sklearn.metrics import r2_score
from sklearn.metrics import mean_squared_error
import seaborn as sns

from scipy import stats

get_ipython().magic(u'matplotlib inline')
style.use('ggplot')


class DataGatherer(object):

    def load_data(self, filename):
        dwnld_data = pd.read_csv(filename, index_col=0)
        dwnld_data.index = pd.to_datetime(dwnld_data.index)
        # print dwnld_data.columns
        return dwnld_data

    def get_data(self, filename):
        # this in the future will handle data from PI directly instead of data
        # from .csv
        return load_data(filename)

class ModelSelector(object):

    def train_model(self, model_data, tar, var, algorithm, mod_type, train_start, train_end, val_start, val_end):
        # Model features

        # 1) Simple model with flat internal load
        if mod_type == 1:
            model_col = var.remove['hdh', 'cdh']
    # 2) Model with Internal Gain profile by time, week and month
        elif mod_type == 2:
            model_col = var
            # turn time of day into dummy variables
            add_var = pd.get_dummies(model_data["TOD"], prefix="TOD_")
            # add all the columns to the model data
            model_data = model_data.join(add_var)
            # full list of variable for regression
            model_col = var + add_var.columns.tolist()

            # turn day of week into dummy variables
            add_var = pd.get_dummies(model_data["DOW"], prefix="DOW_")
            # add all the columns to the model data
            model_data = model_data.join(add_var)
            # full list of variable for regression
            model_col = model_col + add_var.columns.tolist()

            # turn month into dummy variables
            add_var = pd.get_dummies(model_data["MONTH"], prefix="MONTH_")
            # add all the columns to the model data
            model_data = model_data.join(add_var)
            # full list of variable for regression
            model_col = model_col + add_var.columns.tolist()

    # Select Training Set
        # .dropna() # slice training period
        data_train = model_data.loc[train_start:train_end, model_col]
        # if val_start & val_end
        # remove validation intervals
        data_train = data_train.drop(data_train[val_start:val_end].index)
        target_train = model_data.loc[train_start:train_end, tar]  # .dropna()
        target_train = target_train.drop(
            target_train[val_start:val_end].index)  # remove validation intervals

    # Train a simple linear model
        if algorithm == 1:
            clf = linear_model.LinearRegression()
        elif algorithm == 2:
            clf = ensemble.RandomForestRegressor()

        model = clf.fit(data_train, target_train)

    # Save the predicted target
        target_modeled_train = model.predict(data_train)
    # Set negative values (energy) to zero
        target_modeled_train = remove_negative(target_modeled_train)

    # save actual target and predicted target side by side
        compare = pd.DataFrame(target_train)
        compare.columns = ["target_actual"]
        compare["target_predicted"] = target_modeled_train
    # Save the score
        # replace this with functions
        score = model.score(data_train, target_train)

    # Print model coefficients (to see what are the weights)
    #    print "Model variables const + %s" %model_col
    #    print "Model coeff %s + %s"   % (model.intercept_, model.coef_)

        return {"model": model, "data_train": data_train, "target_train": target_train, "model_data": model_data,
                "model_col": model_col, "score": score, "target_modeled_train": target_modeled_train, "compare": compare}

    def predict_model(self, model_data, tar, var, model, val_start, val_end):
        # Select Validation set
        model_col = var
    # select columns and lines
        data_val = model_data.loc[val_start:val_end, model_col]  # .dropna()
        target_val = model_data.loc[val_start:val_end, tar]  # .dropna()

    # Save the predicted target
        target_modeled_val = model.predict(data_val)
    # Set negative values (energy) to zero
        target_modeled_val = remove_negative(target_modeled_val)

    # save actual target and predicted target side by side
        compare = pd.DataFrame(target_val)
        compare.columns = ["target_actual"]
        compare["target_predicted"] = target_modeled_val
    # Save the score
        score = model.score(data_val, target_val)

        return {"score": score, "target_modeled_val": target_modeled_val, "compare": compare}

    def calc_scores(self, compare, p):
        scores = {}

        n = compare.count()[1]
        R2 = r2_score(compare["target_actual"], compare[
                      "target_predicted"])  # this can be negative
        RMSE = (mean_squared_error(compare["target_actual"], compare[
                "target_predicted"]) * n / (n - p))**(0.5)
        CV_RMSE = RMSE * 100 / compare["target_actual"].mean()
        NMBE = compare["target_actual"].sub(compare["target_predicted"]).sum(
        ) / (compare["target_predicted"].mean()) / (n - p) * 100
        scores["Adj_R2"] = 1 - (1 - R2) * (n - 1) / (n - p - 1)
        scores["RMSE"] = RMSE
        scores["CV_RMSE"] = CV_RMSE
        scores["NMBE"] = NMBE
        return scores


class SavingCalculator(object):

    def calc_savings(self, model_data, tar, var, model, val_start, val_end):
        return predict_model(model_data, tar, var, model, val_start, val_end)

    # def savings_table_byMo (data_, tar, cost  ):
    #    data_[tar] = (data_["target_predicted"]-data_["target_actual"])*cost[tar]
    #    #data_[tar+"sav_perc"] = data_[tar]/(data_["target_predicted"]+0.01)*100 for savings %
    #    time_res = "M"
    #    data_table = pd.DataFrame(data_.groupby(pd.TimeGrouper(time_res)).sum()[tar])
    #    return data_table.to_dict()

    def savings_table_byMo(self, data_, tar, cost):
        # for cost savings
        time_res = "M"
        data_cost_sav = {}
        data_perc_sav = {}
        data_ = pd.DataFrame(data_.groupby(pd.TimeGrouper(time_res)).sum())
    # cost savings
        data_[tar] = (data_["target_predicted"] -
                      data_["target_actual"]) * cost[tar]
    # % savings
        data_[tar + "sav_perc"] = (data_["target_predicted"] -
                                   data_["target_actual"]) / (data_["target_predicted"] + 0.01) * 100
        #data_cost_sav = pd.DataFrame(data_.groupby(pd.TimeGrouper(time_res)).sum()).to_dict()
        # data_perc_sav =
        # pd.DataFrame(data_.groupby(pd.TimeGrouper(time_res)).mean()[tar+"sav_perc"])#.to_dict()
        data_cost_sav[tar] = data_[tar].to_dict()
        data_perc_sav[tar] = data_[tar + "sav_perc"].to_dict()
        return {"data_cost_sav": data_cost_sav, "data_perc_sav": data_perc_sav}

    # def calc_uncert(compare_train, confidence, score_tot, tar, absol):
    #    alpha = (100-confidence)/100. #0.05 = 95% confidence ; t-statistic 2-tail
    #    n = (len(compare_train))
    #    t_stat = stats.t.ppf(1-alpha/2, n)
    #    RMSE_val = score_tot[tar]["score_train"]["RMSE"]
    #    smpl_siz = math.sqrt((1+1/(len(compare_train)*1.0)))
    #
    #    if absol == True:
    #        return t_stat*RMSE_val*smpl_siz #absolute error
    #    else:
    # return t_stat*RMSE_val*smpl_siz/compare_sav["target_actual"].mean()*100

    def calc_uncert(self, compare_train, compare_sav, confidence, score_tot, tar, absol):
        alpha = (100 - confidence) / \
            100.  # alpha = 0.05 for 95% confidence ; t-statistic 2-tail
        n = (len(compare_train))  # n samples in training
        m = (len(compare_val))  # m samples in validation

    # adjust n due to autocorrelation of residuals in training (see ASHRAE
    # guideline 14 - annex B2)
        res = compare_train["target_predicted"] - \
            compare_train["target_actual"]
        rho = res.autocorr()
        n_p = n * (1 - rho) / (1 + rho)  # n' in annex B2

        smpl_siz = (n / n_p * (1 + (2 / n_p)) * 1 / m)**0.5
        #smpl_siz = math.sqrt((n+2)/(n*m*1.0))
        sav_perc = (res / compare_train["target_predicted"]).sum() / 100

        t_stat = stats.t.ppf(1 - alpha / 2, n)
        CV_RMSE_val = score_tot[tar]["score_train"]["CV_RMSE"]
        #smpl_siz = math.sqrt((n+2)/(n*m*1.0))

        print n, m, t_stat, CV_RMSE_val, smpl_siz
        if absol:
            return 1.26 * t_stat * CV_RMSE_val * smpl_siz / sav_perc  # +- % error
        else:
            return 1.26 * t_stat * CV_RMSE_val * smpl_siz * (compare_sav["target_actual"].sum())


class Plotter(object):

    def plot_energy_profile_byMo(self, date_start, date_end, data, tar):
        # daily energy profile by Month (each line is an avergage month)
        data_graph = data[date_start: date_end]
        data_graph["YR-MO"] = data_graph.YEAR.astype(int).astype(
            str).str.cat(data_graph.MONTH.astype(int).astype(str), sep='-')
        temp = data_graph.groupby(["TOD", "YR-MO"]).mean()[tar].unstack()
        n = len(temp.columns)
        color = cm.rainbow(np.linspace(0, 1, n))
        temp.plot(figsize=(15, 5), label=tar, color=color,
                  title=tar, ylim=[0, temp.max().max() * 1.1])
        plt.show()

    def plot_WD_WE(self, data, tar):
        WD = data["DOW"] < 5
        WE = data["DOW"] >= 5
        time_res = "d"
        WD_tmp = data[WD].groupby(pd.TimeGrouper(time_res)).mean().loc[:, tar]
        WD_tmp.plot(figsize=(15, 5), style='o', title=tar,
                    ylim=[0, WD_tmp.max() * 1.1])  # WD
        WE_tmp = data[WE].groupby(pd.TimeGrouper(time_res)).mean().loc[:, tar]
        WE_tmp.plot(figsize=(15, 5), style='o', title=tar,
                    ylim=[0, WE_tmp.max() * 1.1])  # WE
        plt.show()

        data_plot = pd.DataFrame()
        data_plot["WD"] = data[WD].groupby(
            pd.TimeGrouper(time_res)).mean().loc[:, tar]
        data_plot["WE"] = data[WE].groupby(
            pd.TimeGrouper(time_res)).mean().loc[:, tar]
        data_plot.plot(kind="box", figsize=(15, 5), title=tar,
                       ylim=[0, data_plot.max().max() * 1.1])
        plt.show()

    def plot_scatter(self, data, tar, x_var, perPre, perPost):
        dataPre = data["PrePost"] == perPre
        dataPost = data["PrePost"] == perPost
        ax = data[dataPre].plot(kind="scatter", x=x_var,
                                y=tar, figsize=(15, 5), title=tar)
        data[dataPost].plot(kind="scatter", x=x_var, y=tar,
                            figsize=(15, 5), color="r", ax=ax)
        plt.show()

    def plot_compare(self, compare_data, plot_start, plot_end):
        compare_data.loc[plot_start:plot_end, :].plot(
            figsize=(15, 5), title=tar)  # .set_title("month = %d" %month)
        plt.show()

    def plot_PrePost_byMo(self, data, tar):
        last_mo = data[data["PrePost"] == 1].index.max().month
        temp = data.groupby(["MONTH", "YEAR"])[tar].mean().unstack()
        temp[(temp.index <= last_mo)].plot(
            figsize=(15, 5), kind="bar", title=tar)
        plt.show()

    def plot_ModPost_byMo(self, compare_sav, tar):
        cols = ["target_predicted", "target_actual"]
        compare_sav = compare_sav.ix[:, cols]
        compare_sav.groupby(compare_sav.index.month).mean().plot(
            figsize=(15, 5), kind="bar", title=tar)
        plt.show()

    def plot_PrePostSav_byMo(self, data, tar):
        last_mo = data[data["PrePost"] == 1].index.max().month
        temp = data.groupby(["MONTH", "YEAR"])[tar].mean().unstack()
        (temp[(temp.index <= last_mo)].diff(axis=1) * (-1)
         ).plot(figsize=(15, 5), kind="bar", title=tar)
        plt.show()

    def plot_ModPostSav_byMo(self, compare_sav, tar):
        cols = ["target_predicted", "target_actual"]
        compare_sav = compare_sav.ix[:, cols]
        (compare_sav.groupby(compare_sav.index.month).mean().diff(
            axis=1) * (-1)).plot(figsize=(15, 5), kind="bar", title=tar)
        plt.show()

    def plot_daily_profile(self, compare_data):
        # add select and group by variables
        compare_data["MONTH"] = compare_data.index.month
        compare_data["TOD"] = compare_data.index.hour
        mi = compare_data["MONTH"].min()
        ma = compare_data["MONTH"].max()

        for month in range(mi, ma + 1):
            cond = compare_data["MONTH"] == month
            col = ['target_actual', 'target_predicted', 'TOD']
            compare_red = compare_data.loc[cond, col]
            compare_grouped = compare_red.groupby("TOD").mean()
            compare_grouped.plot(figsize=(18, 5)).set_title(
                "month = %d" % month)
    #    plt.close()

    def plot_savings(self, compare, time_res):
        compare_val.diff(periods=1, axis=1).iloc[:, 1].groupby(
            pd.TimeGrouper(time_res)).mean().interpolate(method='time').plot(kind="bar", figsize=(10, 5))
