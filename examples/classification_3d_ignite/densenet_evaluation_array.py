# Copyright 2020 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import logging
import numpy as np
import os
import torch
from ignite.engine import create_supervised_evaluator, _prepare_batch
from ignite.metrics import Accuracy
from torch.utils.data import DataLoader

import monai
from monai.data import NiftiDataset
from monai.transforms import Compose, AddChannel, ScaleIntensity, Resize, ToTensor
from monai.handlers import StatsHandler, ClassificationSaver, CheckpointLoader


def main():
    monai.config.print_config()
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    # IXI dataset as a demo, downloadable from https://brain-development.org/ixi-dataset/
    images = [
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI607-Guys-1097-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI175-HH-1570-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI385-HH-2078-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI344-Guys-0905-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI409-Guys-0960-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI584-Guys-1129-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI253-HH-1694-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI092-HH-1436-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI574-IOP-1156-T1.nii.gz"]),
        os.sep.join(["workspace", "data", "medical", "ixi", "IXI-T1", "IXI585-Guys-1130-T1.nii.gz"]),
    ]

    # 2 binary labels for gender classification: man and woman
    labels = np.array([0, 0, 1, 0, 1, 0, 1, 0, 1, 0], dtype=np.int64)

    # define transforms for image
    val_transforms = Compose([ScaleIntensity(), AddChannel(), Resize((96, 96, 96)), ToTensor()])
    # define nifti dataset
    val_ds = NiftiDataset(image_files=images, labels=labels, transform=val_transforms, image_only=False)
    # create DenseNet121
    net = monai.networks.nets.densenet.densenet121(spatial_dims=3, in_channels=1, out_channels=2,)
    device = torch.device("cuda:0")

    metric_name = "Accuracy"
    # add evaluation metric to the evaluator engine
    val_metrics = {metric_name: Accuracy()}

    def prepare_batch(batch, device=None, non_blocking=False):
        return _prepare_batch((batch[0], batch[1]), device, non_blocking)

    # Ignite evaluator expects batch=(img, label) and returns output=(y_pred, y) at every iteration,
    # user can add output_transform to return other values
    evaluator = create_supervised_evaluator(net, val_metrics, device, True, prepare_batch=prepare_batch)

    # add stats event handler to print validation stats via evaluator
    val_stats_handler = StatsHandler(
        name="evaluator",
        output_transform=lambda x: None,  # no need to print loss value, so disable per iteration output
    )
    val_stats_handler.attach(evaluator)

    # for the array data format, assume the 3rd item of batch data is the meta_data
    prediction_saver = ClassificationSaver(
        output_dir="tempdir",
        batch_transform=lambda batch: batch[2],
        output_transform=lambda output: output[0].argmax(1),
    )
    prediction_saver.attach(evaluator)

    # the model was trained by "densenet_training_array" example
    CheckpointLoader(load_path="./runs/net_checkpoint_20.pth", load_dict={"net": net}).attach(evaluator)

    # create a validation data loader
    val_loader = DataLoader(val_ds, batch_size=2, num_workers=4, pin_memory=torch.cuda.is_available())

    state = evaluator.run(val_loader)
    print(state)


if __name__ == "__main__":
    main()
