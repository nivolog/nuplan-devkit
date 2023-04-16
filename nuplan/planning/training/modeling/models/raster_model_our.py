from typing import List

import timm
import torch
from torch import nn

from nuplan.planning.simulation.trajectory.trajectory_sampling import TrajectorySampling
from nuplan.planning.training.modeling.torch_module_wrapper import TorchModuleWrapper
from nuplan.planning.training.modeling.types import FeaturesType, TargetsType
from nuplan.planning.training.preprocessing.feature_builders.abstract_feature_builder import AbstractFeatureBuilder
from nuplan.planning.training.preprocessing.features.raster_our import Raster
from nuplan.planning.training.preprocessing.features.trajectory import Trajectory
from nuplan.planning.training.preprocessing.target_builders.abstract_target_builder import AbstractTargetBuilder

def convert_predictions_to_trajectory(predictions: torch.Tensor) -> torch.Tensor:
    """
    Convert predictions tensor to Trajectory.data shape
    :param predictions: tensor from network
    :return: data suitable for Trajectory
    """
    num_batches = predictions.shape[0]
    return predictions.view(num_batches, -1, Trajectory.state_size())


class RasterModelOur(TorchModuleWrapper):
    """
    Wrapper around raster-based CNN model that consumes ego, agent and map data in rasterized format
    and regresses ego's future trajectory.
    """

    def __init__(
        self,
        feature_builders: List[AbstractFeatureBuilder],
        target_builders: List[AbstractTargetBuilder],
        model_name: str,
        pretrained: bool,
        num_input_channels: int,
        num_features_per_pose: int,
        future_trajectory_sampling: TrajectorySampling,
    ):
        """
        Initialize model.
        :param feature_builders: list of builders for features
        :param target_builders: list of builders for targets
        :param model_name: name of the model (e.g. resnet_50, efficientnet_b3)
        :param pretrained: whether the model will be pretrained
        :param num_input_channels: number of input channel of the raster model.
        :param num_features_per_pose: number of features per single pose
        :param future_trajectory_sampling: parameters of predicted trajectory
        """
        super().__init__(
            feature_builders=feature_builders,
            target_builders=target_builders,
            future_trajectory_sampling=future_trajectory_sampling,
        )

        num_output_features = future_trajectory_sampling.num_poses * num_features_per_pose
        #self._model = timm.create_model(model_name, pretrained=pretrained, num_classes=0, in_chans=num_input_channels)

        #mlp = torch.nn.Linear(in_features=self._model.num_features, out_features=num_output_features)

        #if hasattr(self._model, 'classifier'):
        #    self._model.classifier = mlp
        #elif hasattr(self._model, 'fc'):
        #    self._model.fc = mlp
        #else:
        #    raise NameError('Expected output layer named "classifier" or "fc" in model')
        
        self.layer = nn.Sequential(nn.Conv2d(4, 32, kernel_size=5, stride=1, padding=2),
                                    nn.ReLU(), nn.MaxPool2d(kernel_size=2, stride=2))
        #self.layer2 = nn.Sequential(nn.Conv2d(32, 64, kernel_size=5, stride=1, padding=2), 
        #   nn.ReLU(), nn.MaxPool2d(kernel_size=2, stride=2))
        #self.drop_out = nn.Dropout()
        #self.fc1 = nn.Linear(7*7*32, num_output_features)
        self.fc2 = nn.Linear(112*112*32, num_output_features)



    def forward(self, features: FeaturesType) -> TargetsType:
        """
        Predict
        :param features: input features containing
                        {
                            "raster": Raster,
                        }
        :return: targets: predictions from network
                        {
                            "trajectory": Trajectory,
                        }
        """
        raster: Raster = features["raster"]
	
        out = self.layer(raster.data)
        out = out.reshape(out.size(0), -1)
        predictions = self.fc2(out)
        
        #predictions = self._model.forward(raster.data)
        #print(predictions.size())

        return {"trajectory": Trajectory(data=convert_predictions_to_trajectory(predictions))}
