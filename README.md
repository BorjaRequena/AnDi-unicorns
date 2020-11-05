# Anomalous Unicorns for AnDi Challenge
> Library with the prototyping process of the Anomalous Unicorns team (@ICFO) for the <a href='http://www.andi-challenge.org/'>Anomalous diffusion challenge</a>


The main contributors are Borja Requena, Gorka Muñoz-Gil (co-organizer of the challenge) and Korbinian Kottman, all from ICFO.

The prototyping has been done for the two first tasks of the challenge:
- **Task 1** (regression): anomalous diffusion prediction from variable length trajectories. 
- **Task 2** (classification): diffusion model prediction from variable length trajectories. 

Due to lack of time, we have only been able to train models for 1D trajectories and we have not been able to nail down a model for the third task. For further detail about the tasks, refer to the [official webpage](http://www.andi-challenge.org/) and the [paper](https://arxiv.org/pdf/2003.12036.pdf). 

## Brief model description

We have taken the result of the classification for the regression task, so let us start with Task 2.

For the classification we have leveraged convolutional neural networks (CNNs) and recurrent neural networks (RNNs) to perform the predictions. The predictors are made out of two feature extractors, a CNN and an RNN, that converge into a dense classifier consisting of two fully connected layers. We call this kind of architecture a Hydra, provided that there is one body (the classifier) and several heads that look into the data (the feature extractors). The resulting classifier is an ensemble of these hydras. 

Then, for the regression, we have taken a similar approach building a larger hydra. First, provided that the different diffusion models present quite significant behaviours, we have trained CNNs and RNNs to predict the anomalous exponent of specific diffusion models. With these models, we have built a twelve-head hydra: two feature extractors (CNN, RNN) for each of the five diffusion models and a pre-trained classifier hydra from the previous task. In a sense, the classifier at the end receives the information of each "expert network" together with the information of which one should be considered. The resulting regressor is an ensemble of these hydras.
