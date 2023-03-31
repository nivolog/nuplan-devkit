
# Without jupyter

export NUPLAN_DATA_ROOT="/nuplan-devkit/nuplan/dataset"
export NUPLAN_MAPS_ROOT="/nuplan-devkit/nuplan/dataset/maps"
export NUPLAN_EXP_ROOT="/nuplan-devkit/nuplan/exp"


## To train

python nuplan/planning/script/run_training.py \
    experiment_name=raster_experiment \
    py_func=train \
    +training=training_raster_model \
    scenario_builder=nuplan_mini \
    scenario_filter.limit_total_scenarios=500 \
    lightning.trainer.params.max_epochs=10 \
    data_loader.params.batch_size=8 \
    data_loader.params.num_workers=8


## To validate

python nuplan/planning/script/run_simulation.py \
    +simulation=closed_loop_reactive_agents \
    planner=simple_planner \
    model=raster_model \
    scenario_builder=nuplan_mini \
    scenario_filter=all_scenarios \
    scenario_filter.scenario_types="[near_multiple_vehicles, on_pickup_dropoff, starting_unprotected_cross_turn, high_magnitude_jerk]" \
    scenario_filter.num_scenarios_per_type=10


## Train visualization 

tensorboard --logdir {LOG_DIR} --bind_all


## Validation visualization ( via nuboard )

python nuplan/planning/script/run_nuboard.py