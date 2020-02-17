from lightwood.encoders.datetime.datetime import DatetimeEncoder
from lightwood.encoders.image.img_2_vec import Img2VecEncoder
from lightwood.encoders.image.nn import NnAutoEncoder
from lightwood.encoders.numeric.numeric import NumericEncoder
from lightwood.encoders.text.infersent import InferSentEncoder
from lightwood.encoders.text.rnn import RnnEncoder
from lightwood.encoders.categorical.onehot import OneHotEncoder
from lightwood.encoders.categorical.autoencoder import CategoricalAutoEncoder
from lightwood.encoders.time_series.ts_fresh_ts import TsFreshTsEncoder

try:
    from lightwood.encoders.time_series.cesium_ts import CesiumTsEncoder
    from lightwood.encoders.audio.audio import AmplitudeTsEncoder
    export_optional_encoder = True
except:
    export_optional_encoder = False
    print('Time series encoders can\'t be loaded')

class DateTime:
    DatetimeEncoder = DatetimeEncoder


class Image:
    Img2VecEncoder = Img2VecEncoder
    NnAutoEncoder = NnAutoEncoder


class Numeric:
    NumericEncoder = NumericEncoder


class Text:
    InferSentEncoder = InferSentEncoder
    RnnEncoder = RnnEncoder

class Categorical:
    OneHotEncoder = OneHotEncoder
    CategoricalAutoEncoder = CategoricalAutoEncoder

class TimeSeries:
    TsFreshTsEncoder = TsFreshTsEncoder
    if export_optional_encoder:
        CesiumTsEncoder = CesiumTsEncoder

class Audio:
    if export_optional_encoder:
        AmplitudeTsEncoder = AmplitudeTsEncoder

class BuiltinEncoders:
    DateTime = DateTime
    Image = Image
    Numeric = Numeric
    Text = Text
    Categorical = Categorical
    TimeSeries = TimeSeries
    Audio = Audio


BUILTIN_ENCODERS = BuiltinEncoders
