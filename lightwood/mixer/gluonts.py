from copy import deepcopy
from typing import Dict, Union

import numpy as np
import pandas as pd

from gluonts.dataset.pandas import PandasDataset

from gluonts.model.deepar import DeepAREstimator  # @TODO: support for other estimators
from gluonts.mx import Trainer
from gluonts.mx.trainer.callback import TrainingHistory

from lightwood.helpers.log import log
from lightwood.mixer.base import BaseMixer
from lightwood.api.types import PredictionArguments
from lightwood.data.encoded_ds import EncodedDs, ConcatedEncodedDs


class GluonTSMixer(BaseMixer):
    horizon: int
    target: str
    supports_proba: bool
    model_path: str
    hyperparam_search: bool
    default_config: dict

    def __init__(
            self,
            stop_after: float,
            target: str,
            horizon: int,
            window: int,
            dtype_dict: Dict,
            ts_analysis: Dict,
            n_epochs: int = 10,
            early_stop_patience: int = 3
    ):
        """
        Wrapper around GluonTS probabilistic deep learning models. For now, only DeepAR is supported.

        :param stop_after: time budget in seconds.
        :param target: column to forecast.
        :param horizon: length of forecasted horizon.
        :param window: length of input data.
        :param dtype_dict: data type of each column in the dataset.
        :param ts_analysis: dictionary with miscellaneous time series info, as generated by 'lightwood.data.timeseries_analyzer'.
        :param n_epochs: amount of epochs to train the model for. Will perform early stopping automatically if validation loss degrades.
        :param early_stop_patience: amount of consecutive epochs with no improvement in the validation loss.
        """  # noqa
        super().__init__(stop_after)
        self.stable = True
        self.prepared = False
        self.supports_proba = True
        self.target = target
        self.window = window
        self.horizon = horizon
        self.n_epochs = n_epochs
        self.dtype_dict = dtype_dict
        self.ts_analysis = ts_analysis
        self.grouped_by = ['__default'] if not ts_analysis['tss'].group_by else ts_analysis['tss'].group_by
        self.model = None
        self.train_cache = None
        self.patience = early_stop_patience

    def fit(self, train_data: EncodedDs, dev_data: EncodedDs) -> None:
        """ Fits the model. """  # noqa
        log.info('Started fitting GluonTS forecasting model')

        # prepare data
        cat_ds = ConcatedEncodedDs([train_data, dev_data])
        train_ds = self._make_initial_ds(cat_ds.data_frame, train=True)

        estimator = DeepAREstimator(
            freq=train_ds.freq,
            prediction_length=self.horizon,
            trainer=Trainer(epochs=self.n_epochs, callbacks=[EarlyStop(patience=self.patience)])
        )
        self.model = estimator.train(train_ds)
        log.info('Successfully trained GluonTS forecasting model.')

    def partial_fit(self, train_data: EncodedDs, dev_data: EncodedDs) -> None:
        """
        Due to how lightwood implements the `update` procedure, expected inputs for this method are:

        :param dev_data: original `test` split (used to validate and select model if ensemble is `BestOf`).
        :param train_data: concatenated original `train` and `dev` splits.
        """  # noqa
        self.hyperparam_search = False
        self.fit(dev_data, train_data)
        self.prepared = True

    def __call__(self, ds: Union[EncodedDs, ConcatedEncodedDs],
                 args: PredictionArguments = PredictionArguments()) -> pd.DataFrame:
        """ 
        Calls the mixer to emit forecasts.
        """  # noqa
        length = sum(ds.encoded_ds_lenghts) if isinstance(ds, ConcatedEncodedDs) else len(ds)
        ydf = pd.DataFrame(0,  # zero-filled
                           index=np.arange(length),
                           columns=['prediction', 'lower', 'upper'],
                           dtype=object)
        ydf['index'] = ds.data_frame.index
        conf = args.fixed_confidence if args.fixed_confidence else 0.9
        ydf['confidence'] = conf

        gby = self.ts_analysis["tss"].group_by if self.ts_analysis["tss"].group_by else []
        groups = ds.data_frame[gby[0]].unique() if gby else None

        for idx in range(length):
            df = ds.data_frame.iloc[:idx] if idx != 0 else None
            input_ds = self._make_initial_ds(df, groups=groups)
            forecasts = list(self.model.predict(input_ds))[0]
            ydf.at[idx, 'prediction'] = [entry for entry in forecasts.mean]
            ydf.at[idx, 'lower'] = [entry for entry in forecasts.quantile(1 - conf)]
            ydf.at[idx, 'upper'] = [entry for entry in forecasts.quantile(conf)]

        return ydf

    def _make_initial_ds(self, df=None, train=False, groups=None):
        oby = self.ts_analysis["tss"].order_by
        gby = self.ts_analysis["tss"].group_by if self.ts_analysis["tss"].group_by else []
        freq = self.ts_analysis['sample_freqs']['__default']
        keep_cols = [f'__mdb_original_{oby}', self.target] + [col for col in gby]

        if df is None and not train:
            df = self.train_cache
            if gby:
                df = df[df[gby[0]].isin(groups)]
        else:
            sub_df = df[keep_cols]
            df = deepcopy(sub_df)

            if train:
                self.train_cache = df
            else:
                if gby:
                    cache = self.train_cache[self.train_cache[gby[0]].isin(groups)]
                else:
                    cache = self.train_cache
                df = pd.concat([cache, df]).sort_index()

        df = df.drop_duplicates()  # .reset_index(drop=True)

        if gby:
            df = df.groupby(by=gby[0]).resample(freq).sum().reset_index(level=[0])
            # @TODO: multiple group support and remove groups without enough data
        else:
            df = df.resample(freq).sum()
            gby = '__default_group'
            df[gby] = '__default_group'

        ds = PandasDataset.from_long_dataframe(df, target=self.target, item_id=gby, freq=freq)
        return ds


class EarlyStop(TrainingHistory):
    def __init__(self, patience=3):
        super().__init__()
        self.patience = max(1, patience)
        self.counter = 0

    def on_validation_epoch_end(
        self,
        epoch_no: int,
        epoch_loss: float,
        training_network,
        trainer,
    ) -> bool:
        super().on_validation_epoch_end(epoch_no, epoch_loss, training_network, trainer)

        if len(self.validation_loss_history) > 1:
            if self.validation_loss_history[-1] > self.validation_loss_history[-2]:
                self.counter += 1
            else:
                self.counter = 0  # reset if not successive

        if self.counter >= self.patience:
            return False
        else:
            return True
