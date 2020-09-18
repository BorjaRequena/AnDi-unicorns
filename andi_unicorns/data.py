# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_data.ipynb (unless otherwise specified).

__all__ = ['acquire_data', 'load_data', 'get_discriminative_dls', 'pad_trajectories']

# Cell
from pathlib import Path
import urllib.request as u_request
from zipfile import ZipFile
import csv
import pandas as pd

from fastai.text.all import *

# Cell
def acquire_data(train=True, val=True):
    """Obtains the train and validation datasets of the competition.
    The train url maight fail. Get it from https://drive.google.com/drive/folders/1RXziMCO4Y0Fmpm5bmjcpy-Genhzv4QJ4"""
    data_path = Path("../data")
    data_path.mkdir(exist_ok=True)

    train_url = ("https://doc-4k-88-drive-data-export.googleusercontent.com/download/qh9kfuk2n3khcj0qvrn9t3a4j19nve1a/" +
                "rqpd3tajosn0gta5f9mmbbb1e4u8csnn/1599642000000/17390da5-4567-4189-8a62-1749e1b19b06/108540842544374891611/" +
                "ADt3v-N9HwRAxXINIFMKGcsrjzMlrvhOOYitRyphFom1Ma-CUUekLTkDp75fOegXlyeVVrTPjlnqDaK0g6iI7eDL9YJw91-" +
                "jiityR3iTfrysZP6hpGA62c4lkZbjGp_NJL-XSDUlPcwiVi5Hd5rFtH1YYP0tiiFCoJZsTT4akE8fjdrkZU7vaqFznxuyQDA8YGaiuYlKu" +
                "-F1HiAc9kG_k9EMgkMncNflNJtlugxH5pFcNDdrYiOzIINRIRivt5ScquQ_s4KyuV-zYOQ_g2_VYri8YAg0IqbBrcO-exlp5j-" +
                "t02GDh5JZKU3Hky5b70Z8brCL5lvK0SFAFIKOer45ZrFaACA3HGRNJg==?authuser=0&nonce=k5g7m53pp3cqq&user=" +
                "108540842544374891611&hash=m7kmrh87gmekjhrdcpbhuf1kj13ui0l2")
    val_url = ("https://newcodalab.lri.fr/prod-private/dataset_data_file/None/5a854/development_for_scoring_new.zip?X-" +
               "Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=" +
               "7773750e4e17ea830f574de39161a8a584a70b7a0ebd7baa5bf5401be96cc687&X-Amz-Date=20200909T090404Z&X-Amz" +
               "-Credential=AZIAIOSAODNN7EX123LE%2F20200909%2Fnewcodalab%2Fs3%2Faws4_request")

    if train:
        data = _download_bytes(train_url)
        _write_bytes(data, data_path)
        train_path = data_path/"Development dataset for Training"
        train_path.rename(train_path.parent/"train")

    if val:
        data = _download_bytes(val_url)
        _write_bytes(data, data_path/"val")

def _download_bytes(url):
    "Downloads data from `url` as bytes"
    u = u_request.urlopen(url)
    data = u.read()
    u.close()
    return data

def _write_bytes(data, path):
    "Saves `data` (bytes) into path."
    zip_path = _zip_bytes(data)
    _unzip_file(zip_path, new_path=path)

def _zip_bytes(data, path=None):
    "Saves bytes data as .zip in `path`."
    if path is None: path = Path("../temp")
    zip_path = path.with_suffix(".zip")
    with open(zip_path, "wb") as f:
        f.write(data)
    return zip_path

def _unzip_file(file_path, new_path=None, purge=True):
    "Unzips file in `file_path` to `new_path`."
    if new_path is None: new_path = file_path.with_suffix("")
    zip_path = file_path.with_suffix(".zip")
    with ZipFile(zip_path, 'r') as f:
        f.extractall(new_path)
    if purge: zip_path.unlink()

# Cell
def _txt2df(task, train=True, val=False):
    "Extracts dataset and saves it in df form"
    if train:
        df = pd.DataFrame(columns=['dim', 'y', 'x', 'len'], dtype=object)
        train_path = Path("../data/train")
        if not (train_path/f"task{task}.txt").exists(): acquire_data(train=train, val=val)
        with open(train_path/f"task{task}.txt", "r") as D, open(train_path/f"ref{task}.txt") as Y:
            trajs = csv.reader(D, delimiter=";", lineterminator="\n", quoting=csv.QUOTE_NONNUMERIC)
            labels = csv.reader(Y, delimiter=";", lineterminator="\n", quoting=csv.QUOTE_NONNUMERIC)
            for t, y in zip(trajs, labels):
                dim, x = int(t[0]), t[1:]
                x = tensor(x).view(dim, -1).T
                df = df.append({'dim': dim, 'y': y[1], 'x': x, 'len': len(x)}, ignore_index=True)

        df.to_pickle(train_path/f"task{task}.pkl")

    if val:
        df = pd.DataFrame(columns=['dim', 'x', 'len'], dtype=object)
        val_path = Path("../data/val")
        if not (val_path/f"task{task}.txt").exists(): acquire_data(train=train, val=val)
        with open(val_path/f"task{task}.txt", "r") as D:
            trajs = csv.reader(D, delimiter=";", lineterminator="\n", quoting=csv.QUOTE_NONNUMERIC)
            for t, y in zip(trajs, labels):
                dim, x = int(t[0]), t[1:]
                x = tensor(x).view(dim, -1).T
                df = df.append({'dim': dim, 'x': x, 'len': len(x)}, ignore_index=True)

        df['y'] = ""
        df.to_pickle(val_path/f"task{task}.pkl")

def load_data(task, dim=1, train=True):
    "Loads train or val data of corresponding dimension."
    path = Path("../data/train") if train else Path("../data/val")
    try:
        df = pd.read_pickle(path/f"task{task}.pkl")
    except:
        _txt2df(task, train=train, val=not train)
        df = pd.read_pickle(path/f"task{task}.pkl")
    return df[df['dim']==dim].reset_index()

# Cell
def get_discriminative_dls(task, dim=1, bs=64, split_pct=0.2, train=True, **kwargs):
    "Obtain `DataLoaders` for classification/regression models."
    data = load_data(task, dim=dim, train=train)
    ds = L(zip(data['x'], data['y']))
    idx = L(int(i) for i in torch.randperm(data.shape[0]))
    cut = int(data.shape[0]*split_pct)

    train_ds, val_ds = ds[idx[cut:]], ds[idx[:cut]]
    sorted_dl = partial(SortedDL, before_batch=partial(pad_trajectories, **kwargs), shuffle=True)
    dls = DataLoaders.from_dsets(train_ds, val_ds, bs=bs, dl_type=sorted_dl, device=default_device())

    return dls

def pad_trajectories(samples, pad_value=0, pad_first=True, backwards=False):
    "Pads trajectories assuming shape (len, dim)"
    max_len = max([s.shape[0] for s, _ in samples])
    if backwards: pad_first = not pad_first
    def _pad_sample(s):
        diff = max_len - s.shape[0]
        pad = s.new_zeros((diff, s.shape[1])) + pad_value
        pad_s = torch.cat([pad, s] if pad_first else [s, pad])
        if backwards: pad_s = pad_s.flip(0)
        return pad_s
    return L((_pad_sample(s), y) for s, y in samples)