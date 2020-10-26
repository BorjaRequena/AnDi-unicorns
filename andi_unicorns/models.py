# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_models.ipynb (unless otherwise specified).

__all__ = ['mask_normalisation', 'mask_concat_pool', 'get_act', 'custom_splitter', 'custom_f1', 'MyLearner',
           'RNNLearner', 'MeanPredict', 'Classifier', 'SimpleLSTM', 'ConcatPoolLSTM', 'RegLSTMLin', 'RegLSTM',
           'PoolingClassifier', 'CustomXResNet', 'CNNLin', 'CNN']

# Cell
from fastai.text.all import *
from fastai.vision.all import *

# Cell
def mask_normalisation(x, mask):
    "Normalises each trajectory without taking the mask into account"
    lens = x.shape[1] - mask.sum(dim=1) + 1
    x_with_0 = x.masked_fill(mask, 0)
    mean = x_with_0.sum(dim=1).div_(lens.type(x_with_0.type()))
    x_diff = (x - mean.unsqueeze(-1)).masked_fill(mask, 0)
    sd = x_diff.pow(2).sum(1).div(lens.type(x_with_0.type()) - 1).sqrt()
    return x_diff.div_(sd.unsqueeze(-1))

def mask_concat_pool(output, mask):
    "Pool output of RNN with padding mask into one tensor [last_pool, avg_pool, max_pool]"
    lens = output.shape[1] - mask.sum(dim=1) + 1
    out_with_0 = output.masked_fill(mask, 0)
    out_with_inf = output.masked_fill(mask, -float('inf'))
    avg_pool = out_with_0.sum(dim=1).div_(lens.type(out_with_0.type()))
    max_pool = out_with_inf.max(dim=1)[0]
    return torch.cat([output[:, -1], avg_pool, max_pool], 1)

def get_act(vocab_sz, yrange=None):
    "Provides activation according to regression or classification task."
    if vocab_sz == 1:
        yrange = (0, 2.05) if yrange is None else yrange
        act = SigmoidRange(*yrange)
    else:
        act = nn.Softmax(dim=1)
    return act

def custom_splitter(m):
    "Splits model into parts for freezing. The model should have a `.blocks` property."
    return L([block for block in m.blocks]).map(params)

def custom_f1(y_pred, y):
    "F1 score with activation and prediction to train with `CrossEntropyFlat`"
    return F1Score(average='micro')(y_pred.softmax(1).argmax(1), y)

# Cell
@delegates(Learner.__init__)
class MyLearner(Learner):
    def __init__(self, dls, model, splitter=custom_splitter, path=Path(".."), **kwargs):
        super().__init__(dls, model, splitter=splitter, path=path, **kwargs)

@delegates(Learner.__init__)
class RNNLearner(Learner):
    def __init__(self, dls, model, alpha=2., beta=1., splitter=custom_splitter, path=Path(".."), moms=(0.8,0.7,0.8), **kwargs):
        super().__init__(dls, model, splitter=splitter, moms=moms, path=path, **kwargs)
        self.add_cbs([RNNRegularizer(alpha=alpha, beta=beta)])

# Cell
class MeanPredict:
    def __init__(self):
        self.mean = 0

    def fit(self, y): self.mean = y.mean()
    def predict(self, x): return torch.ones(x.shape[0]) * self.mean

# Cell
class Classifier(Module):
    "Dense classifier"
    def __init__(self, dims, ps, act=True, yrange=None):
        if len(ps) != len(dims)-1: raise ValueError(f"Number of layers {len(dims)} and dropout values {len(ps)} don't match.")
        acts = [nn.ReLU(inplace=True)] * (len(dims) - 2) + [None]
        layers = [LinBnDrop(i, o, p=p, act=a) for i,o,p,a in zip(dims[:-1], dims[1:], ps, acts)]
        if act: layers.append(get_act(dims[-1], yrange=yrange))
        self.layers = nn.Sequential(*layers)

    def forward(self, x): return self.layers(x)

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
                 bidir=False, act=True, norm=False, yrange=(0, 2.05), pad_value=0):
        config = awd_lstm_clas_config
        store_attr('norm,pad_value')
        self.rnn = RegLSTM(dim, h_size, rnn_layers, hidden_p=hid_p, input_p=in_p, weight_p=weight_p, bidir=bidir)

        lin_dim = [h_size*3] + linear_layers + [vocab_sz]
        if ps is None: ps = [0.1]*len(linear_layers)
        ps = [out_ps] + ps
        self.linear = PoolingClassifier(lin_dim, ps=ps, act=act, yrange=yrange)
        self.blocks = [self.rnn, self.linear]

    def forward(self, x):
        mask = x == self.pad_value
        if self.norm: x = mask_normalisation(x, mask)
        out = self.rnn(x)
        x, out, out = self.linear((out, mask))
        return x, out, out

class RegLSTM(Module):
    "LSTM with regularization and inter-layer dropout."
    def __init__(self, dim, n_hid, n_layers, input_p=0.4, hidden_p=0.3, weight_p=0.5, bidir=False):
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
#             new_hidden.append(new_h)
            to_detach(new_h, cpu=False, gather=False)
            if l != self.n_layers-1: output = hid_dp(output)
#         self.hidden = to_detach(new_hidden, cpu=False, gather=False)
        return output

    def _one_rnn(self, n_in, n_out, bidir, weight_p, l):
        "Return one of the inner rnn"
        rnn = nn.LSTM(n_in, n_out, 1, batch_first=True, bidirectional=bidir)
        return WeightDropout(rnn, weight_p)

class PoolingClassifier(Classifier):
    "Pooling linear classifier inspired by `PoolingLinearClassifier`"

    def forward(self, x):
        out, mask = x
        x = mask_concat_pool(out, mask)
        x = self.layers(x)
        return x, out, out

# Cell
class CustomXResNet(nn.Sequential):
    @delegates(ResBlock)
    def __init__(self, block, expansion, layers, p=0.0, c_in=1, n_out=1000, stem_szs=(32,32,64),
                 widen=1.0, sa=False, act_cls=defaults.activation, ndim=1, ks=3, stride=2, **kwargs):
        store_attr('block,expansion,act_cls,ndim,ks')
        if ks % 2 == 0: raise Exception('kernel size has to be odd!')
        stem_szs = [c_in, *stem_szs]
        stem = [ConvLayer(stem_szs[i], stem_szs[i+1], ks=ks, stride=stride if i==0 else 1,
                          act_cls=act_cls, ndim=ndim)
                for i in range(len(stem_szs)-1)]

        n_layers = len(layers)
        block_szs = [stem_szs[-1], 128, 256, 512] + [256]*(n_layers-4)
        block_szs = [int(o*widen) for o in block_szs[:n_layers]]
        block_szs = [stem_szs[-1]//expansion] + block_szs
        blocks    = self._make_blocks(layers, block_szs, sa, stride, **kwargs)

        super().__init__(
            *stem, MaxPool(ks=ks, stride=stride, padding=ks//2, ndim=ndim),
            *blocks, # AdaptiveAvgPool(sz=1, ndim=ndim)
            AdaptiveConcatPool1d(), Flatten(), nn.Dropout(p),
            nn.Linear(2*block_szs[-1]*expansion, n_out),
        )
        init_cnn(self)

    def _make_blocks(self, layers, block_szs, sa, stride, **kwargs):
        return [self._make_layer(ni=block_szs[i], nf=block_szs[i+1], blocks=l,
                                 stride=1 if i==0 else stride, sa=sa and i==len(layers)-4, **kwargs)
                for i,l in enumerate(layers)]

    def _make_layer(self, ni, nf, blocks, stride, sa, **kwargs):
        return nn.Sequential(
            *[self.block(self.expansion, ni if i==0 else nf, nf, stride=stride if i==0 else 1,
                      sa=sa and i==(blocks-1), act_cls=self.act_cls, ndim=self.ndim, ks=self.ks, **kwargs)
              for i in range(blocks)])

# Cell
@delegates(CustomXResNet.__init__)
class CNNLin(Module):
    def __init__(self, dim, vocab_sz=1, h_size=1000, yrange=(0, 2.05), exp=1, layers=[1, 1, 1, 1], p=0., **kwargs):
        self.cnn = CNN(dim, exp=exp, layers=layers, p=p, n_out=h_size, **kwargs)
        self.lin = LinBnDrop(h_size, vocab_sz, p=p, act=get_act(vocab_sz, yrange))
        self.blocks = [self.cnn, self.lin]

    def forward(self, x):
        mask = x == 0
        x = mask_normalisation(x, mask)
        x = self.cnn(x.permute(0, 2, 1))
        return self.lin(x)

@delegates(CustomXResNet.__init__)
class CNN(CustomXResNet):
    def __init__(self, dim, exp=1, layers=[1, 1], **kwargs):
        super().__init__(ResBlock, exp, layers, c_in=dim, ndim=1, **kwargs)