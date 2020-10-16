# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_models.ipynb (unless otherwise specified).

__all__ = ['MeanPredict', 'SimpleLSTM', 'ConcatPoolLSTM', 'RegLSTMLin', 'RegLSTM', 'PoolingClassifier']

# Cell
from fastai.text.all import *

# Cell
class MeanPredict:
    def __init__(self):
        self.mean = 0

    def fit(self, y): self.mean = y.mean()
    def predict(self, x): return torch.ones(x.shape[0]) * self.mean

# Cell
class SimpleLSTM(Module):
    "Cheap and simple LSTM running through the trajectories."
    def __init__(self, dim, h_size, vocab_sz, bs, n_layers=1, yrange=(0, 2.05)):
        self.rnn = nn.LSTM(dim, h_size, n_layers, batch_first=True)
        self.h_o = nn.Linear(h_size, vocab_sz)
        self.h = [torch.zeros(n_layers, bs, h_size) for _ in range(2)] # In case we do a generative
        self.sigmoid = SigmoidRange(*yrange)

    def forward(self, x):
        res, h = self.rnn(x) # res[bs, len, h_size],
        self.h = [h_.detach() for h_ in h]
        avg_pool = res.mean(1)   # Poorly done avg pooling
        out = self.h_o(avg_pool)
        return self.sigmoid(out).squeeze()

    def reset(self):
        for h in self.h: h.zero_()

# Cell
class ConcatPoolLSTM(Module):
    "LSTM with last, avg & max pooling."
    def __init__(self, dim, h_size, vocab_sz, n_layers=1, bidir=False, yrange=(0, 2.05), pad_value=0):
        self.pad_value = pad_value
        self.rnn = nn.LSTM(dim, h_size, n_layers, batch_first=True, bidirectional=bidir)
        self.h_o = nn.Linear(3*h_size, vocab_sz)
        self.sigmoid = SigmoidRange(*yrange)

    def forward(self, x):
        res, h = self.rnn(x)
        for h_ in h: h_.detach()
        mask = x == self.pad_value
        pool = mask_concat_pool(res, mask)
        out = self.h_o(pool)
        return self.sigmoid(out).squeeze()

# Cell
class RegLSTMLin(Module):
    "LSTM with dropout and batch norm."
    def __init__(self, dim, h_size, vocab_sz=1, rnn_layers=1, in_p=0.4, hid_p=0.3, weight_p=0.5, out_ps=0.4, linear_layers=[200, 50], ps=None,
                 bidir=False, yrange=(0, 2.05), pad_value=0):
        config = awd_lstm_clas_config
        self.pad_value = pad_value
        self.rnn = RegLSTM(dim, h_size, rnn_layers, hidden_p=hid_p, input_p=in_p, weight_p=weight_p, bidir=bidir)

        lin_dim = [h_size*3] + linear_layers + [vocab_sz]
        if ps is None: ps = [0.1]*len(linear_layers)
        ps = [out_ps] + ps
        self.linear = PoolingClassifier(lin_dim, ps=ps, yrange=yrange)

    def forward(self, x):
        mask = x == self.pad_value
        x = mask_normalisation(x, mask)
        out = self.rnn(x)
        x, _, _ = self.linear((out, mask))
        return x

class RegLSTM(Module):
    "LSTM with regularization and inter-layer dropout."
    def __init__(self, dim, n_hid, n_layers, hidden_p=0.3, input_p=0.4, weight_p=0.5, bidir=False):
        store_attr('dim,n_hid,n_layers')
        self.n_dir = 2 if bidir else 1
        self.rnns = nn.ModuleList([self._one_rnn(dim if l == 0 else n_hid, n_hid//self.n_dir,
                                                 bidir, weight_p, l) for l in range(n_layers)])
        self.input_dp = RNNDropout(input_p)
        self.hidden_dps = nn.ModuleList([RNNDropout(hidden_p) for l in range(n_layers)])

    def forward(self, x):
        output = self.input_dp(x)
        new_hidden = []
        for l, (rnn,hid_dp) in enumerate(zip(self.rnns, self.hidden_dps)):
            output, new_h = rnn(output)
            new_hidden.append(new_h)
            if l != self.n_layers-1: output = hid_dp(output)
        self.hidden = to_detach(new_hidden, cpu=False, gather=False)
        return output

    def _one_rnn(self, n_in, n_out, bidir, weight_p, l):
        "Return one of the inner rnn"
        rnn = nn.LSTM(n_in, n_out, 1, batch_first=True, bidirectional=bidir)
        return WeightDropout(rnn, weight_p)

class PoolingClassifier(Module):
    "Pooling linear classifier inspired by `PoolingLinearClassifier`"
    def __init__(self, dims, ps, yrange=None):
        if len(ps) != len(dims)-1: raise ValueError(f"Number of layers {len(dims)} and dropout values {len(ps)} don't match.")
        acts = [nn.ReLU(inplace=True)] * (len(dims) - 2) + [None]
        layers = [LinBnDrop(i, o, p=p, act=a) for i,o,p,a in zip(dims[:-1], dims[1:], ps, acts)]
        layers.append(get_act(dims[-1], yrange=yrange))
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        out, mask = x
        x = mask_concat_pool(out, mask)
        x = self.layers(x)
        return x, out, out