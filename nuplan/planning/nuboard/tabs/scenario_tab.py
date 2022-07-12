import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from math import ceil
from typing import Any, Dict, List, Optional

import numpy as np
import numpy.typing as npt
import pandas
from bokeh.document.document import Document
from bokeh.layouts import LayoutDOM, column, gridplot, layout
from bokeh.models import ColumnDataSource, Div, HoverTool, Select
from bokeh.models.callbacks import CustomJS
from bokeh.plotting.figure import Figure

from nuplan.common.actor_state.vehicle_parameters import VehicleParameters
from nuplan.planning.nuboard.base.base_tab import BaseTab
from nuplan.planning.nuboard.base.experiment_file_data import ExperimentFileData
from nuplan.planning.nuboard.base.simulation_tile import SimulationTile
from nuplan.planning.nuboard.style import PLOT_PALETTE, default_div_style, scenario_tab_style
from nuplan.planning.scenario_builder.abstract_scenario_builder import AbstractScenarioBuilder

logger = logging.getLogger(__name__)


@dataclass
class ScenarioMetricScoreData:
    """Metric final score data for each scenario in the scenario tab."""

    experiment_index: int  # Experiment index to represent color
    metric_aggregator_file_name: str  # Aggregator file name
    metric_aggregator_file_index: int  # Index of a metric aggregator file in a folder
    planner_name: str  # Planner name
    metric_statistic_name: str  # Metric statistic name
    score: float  # Metric score, some metrics have not a score (none instead of 0)


@dataclass
class ScenarioMetricScoreDataSource:
    """Data source for each scenario metric final score figure."""

    xs: List[str]  # A list of x axis values
    ys: List[float]  # A list of y axis values
    planners: List[str]  # A list of planner names
    aggregators: List[str]  # A list of aggregator file names
    experiments: List[str]  # A list of experiment file names
    fill_colors: List[str]  # A list of fill colors
    marker: str  # Marker
    legend_label: str  # Legend label name


@dataclass
class ScenarioTimeSeriesData:
    """Time series data in the scenario tab."""

    experiment_index: int  # Experiment index to represent color.
    planner_name: str  # Planner name
    time_series_values: npt.NDArray[np.float64]  # A list of time series values
    time_series_timestamps: List[int]  # A list of time series timestamps
    time_series_unit: str  # Time series unit


# Type for scenario metric score data type: {log name: {scenario name: metric score data}}
scenario_metric_score_dict_type = Dict[str, Dict[str, List[ScenarioMetricScoreData]]]


class ScenarioTab(BaseTab):
    """Scenario tab in nuboard."""

    def __init__(
        self,
        doc: Document,
        experiment_file_data: ExperimentFileData,
        vehicle_parameters: VehicleParameters,
        scenario_builder: AbstractScenarioBuilder,
    ):
        """
        Scenario tab to render metric results about a scenario.
        :param doc: Bokeh HTML document.
        :param experiment_file_data: Experiment file data.
        :param vehicle_parameters: Vehicle parameters.
        :param scenario_builder: nuPlan scenario builder instance.
        """
        super().__init__(doc=doc, experiment_file_data=experiment_file_data)
        self._number_metrics_per_figure: int = 4
        self.planner_checkbox_group.name = "scenario_planner_checkbox_group"
        self._scenario_builder = scenario_builder

        # UI.
        self._scalar_scenario_type_select = Select(
            name="scenario_scalar_scenario_type_select",
            css_classes=["scalar-scenario-type-select"],
        )
        self._scalar_scenario_type_select.on_change("value", self._scalar_scenario_type_select_on_change)
        self._scalar_log_name_select = Select(
            name="scenario_scalar_log_name_select",
            css_classes=["scalar-log-name-select"],
        )
        self._scalar_log_name_select.on_change("value", self._scalar_log_name_select_on_change)

        self._scalar_scenario_name_select = Select(
            name="scenario_scalar_scenario_name_select",
            css_classes=["scalar-scenario-name-select"],
        )
        self._scalar_scenario_name_select.on_change("value", self._scalar_scenario_name_select_on_change)
        self._loading_js = CustomJS(
            args={},
            code="""
            document.getElementById('scenario-loading').style.visibility = 'visible';
            document.getElementById('scenario-plot-section').style.visibility = 'hidden';
            cb_obj.tags = [window.outerWidth, window.outerHeight];
        """,
        )
        self._scalar_scenario_name_select.js_on_change("value", self._loading_js)
        self.planner_checkbox_group.js_on_change("active", self._loading_js)
        self._default_time_series_div = Div(
            text=""" <p> No time series results, please add more experiments or
                adjust the search filter.</p>""",
            css_classes=['scenario-default-div'],
            margin=default_div_style['margin'],
            width=default_div_style['width'],
        )
        self._time_series_layout = column(
            self._default_time_series_div,
            css_classes=["scenario-time-series-layout"],
            name="time_series_layout",
        )

        self._default_simulation_div = Div(
            text=""" <p> No simulation data, please add more experiments or
                adjust the search filter.</p>""",
            css_classes=['scenario-default-div'],
            margin=default_div_style['margin'],
            width=default_div_style['width'],
        )
        self._simulation_tile_layout = column(
            self._default_simulation_div,
            css_classes=["scenario-simulation-layout"],
            name="simulation_tile_layout",
        )
        self._end_loading_js = CustomJS(
            args={},
            code="""
            document.getElementById('scenario-loading').style.visibility = 'hidden';
            document.getElementById('scenario-plot-section').style.visibility = 'visible';
        """,
        )
        self._simulation_tile_layout.js_on_change("children", self._end_loading_js)
        self.simulation_tile = SimulationTile(
            map_factory=self._scenario_builder.get_map_factory(),
            doc=self._doc,
            vehicle_parameters=vehicle_parameters,
            experiment_file_data=experiment_file_data,
        )

        self._default_scenario_score_div = Div(
            text=""" <p> No scenario score results, please add more experiments or
                        adjust the search filter.</p>""",
            css_classes=['scenario-default-div'],
            margin=default_div_style['margin'],
            width=default_div_style['width'],
        )
        self._scenario_score_layout = column(
            self._default_scenario_score_div,
            css_classes=["scenario-score-layout"],
            name="scenario_score_layout",
        )

        self._scenario_metric_score_data_figure_sizes = scenario_tab_style['scenario_metric_score_figure_sizes']
        self._scenario_metric_score_data: scenario_metric_score_dict_type = {}
        self._time_series_data: Dict[str, List[ScenarioTimeSeriesData]] = {}
        self._simulation_figure_data: List[Any] = []
        self._available_scenario_names: List[str] = []
        self._simulation_plots: Optional[column] = None
        self._init_selection()

    @property
    def scalar_scenario_type_select(self) -> Select:
        """Return scalar_scenario_type_select."""
        return self._scalar_scenario_type_select

    @property
    def scalar_log_name_select(self) -> Select:
        """Return scalar_log_name_select."""
        return self._scalar_log_name_select

    @property
    def scalar_scenario_name_select(self) -> Select:
        """Return scalar_scenario_name_select."""
        return self._scalar_scenario_name_select

    @property
    def time_series_layout(self) -> column:
        """Return time_series_layout."""
        return self._time_series_layout

    @property
    def scenario_score_layout(self) -> column:
        """Return scenario_score_layout."""
        return self._scenario_score_layout

    @property
    def simulation_tile_layout(self) -> column:
        """Return simulation_tile_layout."""
        return self._simulation_tile_layout

    def file_paths_on_change(
        self, experiment_file_data: ExperimentFileData, experiment_file_active_index: List[int]
    ) -> None:
        """
        Interface to update layout when file_paths is changed.
        :param experiment_file_data: Experiment file data.
        :param experiment_file_active_index: Active indexes for experiment files.
        """
        self._experiment_file_data = experiment_file_data
        self._experiment_file_active_index = experiment_file_active_index

        self.simulation_tile.init_simulations(figure_sizes=self.simulation_figure_sizes)
        self._init_selection()
        self._scenario_metric_score_data = self._update_aggregation_metric()
        self._update_scenario_plot()

    def _click_planner_checkbox_group(self, attr: Any) -> None:
        """
        Click event handler for planner_checkbox_group.
        :param attr: Clicked attributes.
        """
        # Render scenario metric figures
        scenario_metric_score_figure_data = self._render_scenario_metric_score()

        # Render scenario metric score layout
        scenario_metric_score_layout = self._render_scenario_metric_layout(
            figure_data=scenario_metric_score_figure_data,
            default_div=self._default_scenario_score_div,
            plot_width=self._scenario_metric_score_data_figure_sizes[0],
            legend=False,
        )
        self._scenario_score_layout.children[0] = layout(scenario_metric_score_layout)

        # Filter time series data
        filtered_time_series_data: Dict[str, List[ScenarioTimeSeriesData]] = defaultdict(list)
        for key, time_series_data in self._time_series_data.items():
            for data in time_series_data:
                if data.planner_name not in self.enable_planner_names:
                    continue
                filtered_time_series_data[key].append(data)

        # Render time series figure data
        time_series_figure_data = self._render_time_series(aggregated_time_series_data=filtered_time_series_data)

        # Render time series layout
        time_series_figures = self._render_scenario_metric_layout(
            figure_data=time_series_figure_data,
            default_div=self._default_time_series_div,
            plot_width=self.plot_sizes[0],
            legend=True,
        )
        self._time_series_layout.children[0] = layout(time_series_figures)

        # Render simulation
        filtered_simulation_figures = [
            data.plot for data in self._simulation_figure_data if data.planner_name in self.enable_planner_names
        ]
        if not filtered_simulation_figures:
            simulation_layouts = column(self._default_simulation_div)
        else:
            simulation_layouts = gridplot(
                filtered_simulation_figures,
                ncols=self.get_plot_cols(plot_width=self.simulation_figure_sizes[0]),
                toolbar_location=None,
            )
        self._simulation_tile_layout.children[0] = layout(simulation_layouts)

    def _update_simulation_layouts(self) -> None:
        """Update simulation layouts."""
        self._simulation_tile_layout.children[0] = layout(self._simulation_plots)

    def _update_scenario_plot(self) -> None:
        """Update scenario plots when selection is made."""
        start_time = time.perf_counter()

        # Render scenario metric score figure data
        scenario_metric_score_figure_data = self._render_scenario_metric_score()

        # Render scenario metric score layout
        scenario_metric_score_layout = self._render_scenario_metric_layout(
            figure_data=scenario_metric_score_figure_data,
            default_div=self._default_scenario_score_div,
            plot_width=self._scenario_metric_score_data_figure_sizes[0],
            legend=False,
        )
        self._scenario_score_layout.children[0] = layout(scenario_metric_score_layout)

        # Aggregate time series data
        self._time_series_data = self._aggregate_time_series_data()

        # Render time series figure data
        time_series_figure_data = self._render_time_series(aggregated_time_series_data=self._time_series_data)

        # Render time series layout
        time_series_figures = self._render_scenario_metric_layout(
            figure_data=time_series_figure_data,
            default_div=self._default_time_series_div,
            plot_width=self.plot_sizes[0],
            legend=True,
        )
        self._time_series_layout.children[0] = layout(time_series_figures)

        # Render simulations.
        self._simulation_plots = self._render_simulations()

        # Make sure the simulation plot upgrades at the last
        self._doc.add_next_tick_callback(self._update_simulation_layouts)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.debug(f"Rending scenario plot takes {elapsed_time:.4f} seconds.")

    def _update_planner_names(self) -> None:
        """Update planner name options in the checkbox widget."""
        self.planner_checkbox_group.labels = []
        self.planner_checkbox_group.active = []
        selected_keys = [
            key
            for key in self.experiment_file_data.simulation_scenario_keys
            if key.scenario_type == self._scalar_scenario_type_select.value
            and key.scenario_name == self._scalar_scenario_name_select.value
        ]
        sorted_planner_names = sorted(list({key.planner_name for key in selected_keys}))
        self.planner_checkbox_group.labels = sorted_planner_names
        self.planner_checkbox_group.active = [index for index in range(len(sorted_planner_names))]

    def _scalar_scenario_type_select_on_change(self, attr: str, old: str, new: str) -> None:
        """
        Helper function to change event in scalar scenario type.
        :param attr: Attribute.
        :param old: Old value.
        :param new: New value.
        """
        if new == "":
            return

        available_log_names = self.load_log_name(scenario_type=self._scalar_scenario_type_select.value)
        self._scalar_log_name_select.options = [""] + available_log_names
        self._scalar_log_name_select.value = ""

    def _scalar_log_name_select_on_change(self, attr: str, old: str, new: str) -> None:
        """
        Helper function to change event in scalar log name.
        :param attr: Attribute.
        :param old: Old value.
        :param new: New value.
        """
        if new == "":
            return

        available_scenario_names = self.load_scenario_names(
            scenario_type=self._scalar_scenario_type_select.value, log_name=self._scalar_log_name_select.value
        )
        self._scalar_scenario_name_select.options = [""] + available_scenario_names
        self._scalar_scenario_name_select.value = ""

    def _scalar_scenario_name_select_on_change(self, attr: str, old: str, new: str) -> None:
        """
        Helper function to change event in scalar scenario name.
        :param attr: Attribute.
        :param old: Old value.
        :param new: New value.
        """
        if self._scalar_scenario_name_select.tags:
            self.window_width = self._scalar_scenario_name_select.tags[0]
            self.window_height = self._scalar_scenario_name_select.tags[1]
        self._update_planner_names()
        self._update_scenario_plot()

    def _init_selection(self) -> None:
        """Init histogram and scalar selection options."""
        self._scalar_scenario_type_select.value = ""
        self._scalar_scenario_type_select.options = []
        self._scalar_log_name_select.value = ""
        self._scalar_log_name_select.options = []
        self._scalar_scenario_name_select.value = ""
        self._scalar_scenario_name_select.options = []
        self._available_scenario_names = []

        if len(self._scalar_scenario_type_select.options) == 0:
            self._scalar_scenario_type_select.options = [""] + self.experiment_file_data.available_scenario_types

        if len(self._scalar_scenario_type_select.options) > 0:
            self._scalar_scenario_type_select.value = self._scalar_scenario_type_select.options[0]

        self._update_planner_names()

    @staticmethod
    def _render_scalar_figure(
        title: str,
        y_axis_label: str,
        hover: HoverTool,
        sizes: List[int],
        x_axis_label: Optional[str] = None,
        x_range: Optional[List[str]] = None,
        y_range: Optional[List[str]] = None,
    ) -> Figure:
        """
        Render a scalar figure.
        :param title: Plot title.
        :param y_axis_label: Y axis label.
        :param hover: Hover tool for the plot.
        :param sizes: Width and height in pixels.
        :param x_axis_label: Label in x axis.
        :param x_range: Labels in x major axis.
        :param y_range: Labels in y major axis.
        :return A time series plot.
        """
        scenario_scalar_figure = Figure(
            background_fill_color=PLOT_PALETTE["background_white"],
            title=title,
            css_classes=["time-series-figure"],
            margin=scenario_tab_style["time_series_figure_margins"],
            width=sizes[0],
            height=sizes[1],
            active_scroll="wheel_zoom",
            output_backend="webgl",
            x_range=x_range,
            y_range=y_range,
        )
        scenario_scalar_figure.add_tools(hover)

        scenario_scalar_figure.title.text_font_size = scenario_tab_style["time_series_figure_title_text_font_size"]
        scenario_scalar_figure.xaxis.axis_label_text_font_size = scenario_tab_style[
            "time_series_figure_xaxis_axis_label_text_font_size"
        ]
        scenario_scalar_figure.xaxis.major_label_text_font_size = scenario_tab_style[
            "time_series_figure_xaxis_major_label_text_font_size"
        ]
        scenario_scalar_figure.yaxis.axis_label_text_font_size = scenario_tab_style[
            "time_series_figure_yaxis_axis_label_text_font_size"
        ]
        scenario_scalar_figure.yaxis.major_label_text_font_size = scenario_tab_style[
            "time_series_figure_yaxis_major_label_text_font_size"
        ]
        scenario_scalar_figure.toolbar.logo = None

        # Rotate the x_axis label with 45 (180/4) degrees.
        scenario_scalar_figure.xaxis.major_label_orientation = np.pi / 4

        scenario_scalar_figure.yaxis.axis_label = y_axis_label
        scenario_scalar_figure.xaxis.axis_label = x_axis_label

        return scenario_scalar_figure

    def _update_aggregation_metric(self) -> scenario_metric_score_dict_type:
        """
        Update metric score for each scenario.
        :return A dict of log name: {scenario names and their metric scores}.
        """
        data: scenario_metric_score_dict_type = defaultdict(lambda: defaultdict(list))
        # Loop through all metric aggregators
        for index, metric_aggregator_dataframes in enumerate(self.experiment_file_data.metric_aggregator_dataframes):
            if index not in self._experiment_file_active_index:
                continue
            for file_index, (metric_aggregator_filename, metric_aggregator_dataframe) in enumerate(
                metric_aggregator_dataframes.items()
            ):
                # Get columns
                columns = set(list(metric_aggregator_dataframe.columns))
                # List of non-metric columns to be excluded
                non_metric_columns = {
                    'scenario',
                    'log_name',
                    'scenario_type',
                    'num_scenarios',
                    'planner_name',
                    'aggregator_type',
                }
                metric_columns = sorted(list(columns - non_metric_columns))
                # Iterate through rows
                for _, row_data in metric_aggregator_dataframe.iterrows():
                    num_scenarios = row_data["num_scenarios"]
                    if not np.isnan(num_scenarios):
                        continue

                    planner_name = row_data["planner_name"]
                    scenario_name = row_data["scenario"]
                    log_name = row_data["log_name"]
                    for metric_column in metric_columns:
                        score = row_data[metric_column]
                        # Add scenario metric score data
                        if score is not None:
                            data[log_name][scenario_name].append(
                                ScenarioMetricScoreData(
                                    experiment_index=index,
                                    metric_aggregator_file_name=metric_aggregator_filename,
                                    metric_aggregator_file_index=file_index,
                                    planner_name=planner_name,
                                    metric_statistic_name=metric_column,
                                    score=np.round(score, 4),
                                )
                            )

        return data

    def _aggregate_time_series_data(self) -> Dict[str, List[ScenarioTimeSeriesData]]:
        """
        Aggregate time series data.
        :return A dict of metric statistic names and their data.
        """
        aggregated_time_series_data: Dict[str, List[ScenarioTimeSeriesData]] = {}
        scenario_types = (
            tuple([self._scalar_scenario_type_select.value]) if self._scalar_scenario_type_select.value else None
        )
        log_names = tuple([self._scalar_log_name_select.value]) if self._scalar_log_name_select.value else None

        if not len(self._scalar_scenario_name_select.value):
            return aggregated_time_series_data

        for index, metric_statistics_dataframes in enumerate(self.experiment_file_data.metric_statistics_dataframes):
            if index not in self._experiment_file_active_index:
                continue

            for metric_statistics_dataframe in metric_statistics_dataframes:
                planner_names = metric_statistics_dataframe.planner_names
                if metric_statistics_dataframe.metric_statistic_name not in aggregated_time_series_data:
                    aggregated_time_series_data[metric_statistics_dataframe.metric_statistic_name] = []
                for planner_name in planner_names:
                    data_frame = metric_statistics_dataframe.query_scenarios(
                        scenario_names=tuple([str(self._scalar_scenario_name_select.value)]),
                        scenario_types=scenario_types,
                        planner_names=tuple([planner_name]),
                        log_names=log_names,
                    )
                    if not len(data_frame):
                        continue

                    time_series_headers = metric_statistics_dataframe.time_series_headers
                    time_series: pandas.DataFrame = data_frame[time_series_headers]
                    if time_series[time_series_headers[0]].iloc[0] is None:
                        continue

                    time_series_values: npt.NDArray[np.float64] = np.round(
                        np.asarray(
                            list(
                                chain.from_iterable(time_series[metric_statistics_dataframe.time_series_values_column])
                            )
                        ),
                        4,
                    )

                    time_series_timestamps = list(
                        chain.from_iterable(time_series[metric_statistics_dataframe.time_series_timestamp_column])
                    )
                    time_series_unit = time_series[metric_statistics_dataframe.time_series_unit_column].iloc[0]

                    scenario_time_series_data = ScenarioTimeSeriesData(
                        experiment_index=index,
                        planner_name=planner_name,
                        time_series_values=time_series_values,
                        time_series_timestamps=time_series_timestamps,
                        time_series_unit=time_series_unit,
                    )

                    aggregated_time_series_data[metric_statistics_dataframe.metric_statistic_name].append(
                        scenario_time_series_data
                    )

        return aggregated_time_series_data

    def _render_time_series(
        self, aggregated_time_series_data: Dict[str, List[ScenarioTimeSeriesData]]
    ) -> Dict[str, Figure]:
        """
        Render time series plots.
        :param aggregated_time_series_data: Aggregated scenario time series data.
        :return A dict of figure name and figures.
        """
        time_series_figures: Dict[str, Figure] = {}
        for metric_statistic_name, scenario_time_series_data in aggregated_time_series_data.items():
            for data in scenario_time_series_data:
                if not len(data.time_series_values):
                    continue

                if metric_statistic_name not in time_series_figures:
                    time_series_figures[metric_statistic_name] = self._render_scalar_figure(
                        title=metric_statistic_name,
                        y_axis_label=data.time_series_unit,
                        x_axis_label='frame',
                        hover=HoverTool(
                            tooltips=[
                                ("Frame", "@x"),
                                ("Value", "@y{0.0000}"),
                                ("Time_us", "@time_us"),
                                ("Planner", "$name"),
                            ]
                        ),
                        sizes=self.plot_sizes,
                    )
                planner_name = data.planner_name + f" ({self.get_file_path_last_name(data.experiment_index)})"
                color = self.experiment_file_data.file_path_colors[data.experiment_index][data.planner_name]
                time_series_figure = time_series_figures[metric_statistic_name]
                data_source = ColumnDataSource(
                    dict(
                        x=list(range(len(data.time_series_values))),
                        y=data.time_series_values,
                        time_us=data.time_series_timestamps,
                    )
                )
                time_series_figure.line(
                    x="x", y="y", name=planner_name, color=color, legend_label=planner_name, source=data_source
                )

        return time_series_figures

    def _render_scenario_metric_score_scatter(
        self, scatter_figure: Figure, scenario_metric_score_data: Dict[str, List[ScenarioMetricScoreData]]
    ) -> None:
        """
        Render scatter plot with scenario metric score data.
        :param scatter_figure: A scatter figure.
        :param scenario_metric_score_data: Metric score data for a scenario.
        """
        # Aggregate data sources
        data_sources: Dict[str, ScenarioMetricScoreDataSource] = {}
        for metric_name, metric_score_data in scenario_metric_score_data.items():
            for index, score_data in enumerate(metric_score_data):
                experiment_name = self.get_file_path_last_name(score_data.experiment_index)
                legend_label = f"{score_data.planner_name} ({experiment_name})"
                data_source_index = legend_label + f" - {score_data.metric_aggregator_file_index})"
                if data_source_index not in data_sources:
                    data_sources[data_source_index] = ScenarioMetricScoreDataSource(
                        xs=[],
                        ys=[],
                        planners=[],
                        aggregators=[],
                        experiments=[],
                        fill_colors=[],
                        marker=self.get_scatter_sign(score_data.metric_aggregator_file_index),
                        legend_label=legend_label,
                    )
                fill_color = self.experiment_file_data.file_path_colors[score_data.experiment_index][
                    score_data.planner_name
                ]
                data_sources[data_source_index].xs.append(score_data.metric_statistic_name)
                data_sources[data_source_index].ys.append(score_data.score)
                data_sources[data_source_index].planners.append(score_data.planner_name)
                data_sources[data_source_index].aggregators.append(score_data.metric_aggregator_file_name)
                data_sources[data_source_index].experiments.append(
                    self.get_file_path_last_name(score_data.experiment_index)
                )
                data_sources[data_source_index].fill_colors.append(fill_color)

        # Plot scatter
        for legend_label, data_source in data_sources.items():
            sources = ColumnDataSource(
                dict(
                    xs=data_source.xs,
                    ys=data_source.ys,
                    planners=data_source.planners,
                    experiments=data_source.experiments,
                    aggregators=data_source.aggregators,
                    fill_colors=data_source.fill_colors,
                    line_colors=data_source.fill_colors,
                )
            )
            glyph_renderer = self.get_scatter_render_func(
                scatter_sign=data_source.marker, scatter_figure=scatter_figure
            )
            glyph_renderer(x="xs", y="ys", size=10, fill_color="fill_colors", line_color="fill_colors", source=sources)

    def _render_scenario_metric_score(self) -> Dict[str, Figure]:
        """
        Render scenario metric score plot.
        :return A dict of figure names and figures.
        """
        if (
            not self._scalar_log_name_select.value
            or not self._scalar_scenario_name_select.value
            or not self._scenario_metric_score_data
        ):
            return {}
        selected_scenario_metric_score: List[ScenarioMetricScoreData] = self._scenario_metric_score_data[
            self._scalar_log_name_select.value
        ][self._scalar_scenario_name_select.value]
        # Rearranged to {metric_statistic_namae: List[scenario_metric_score_data]}
        data: Dict[str, List[ScenarioMetricScoreData]] = defaultdict(list)
        for scenario_metric_score_data in selected_scenario_metric_score:
            if scenario_metric_score_data.planner_name not in self.enable_planner_names:
                continue

            # Rename final score from score to scenario_score
            metric_statistic_name = scenario_metric_score_data.metric_statistic_name
            data[metric_statistic_name].append(scenario_metric_score_data)
        metric_statistic_names = sorted(list(set(data.keys())))
        # Make sure the final score of a scenario is the last element
        if 'score' in metric_statistic_names:
            metric_statistic_names.remove('score')
            metric_statistic_names.append('score')
        hover = HoverTool(
            tooltips=[
                ("Metric", "@xs"),
                ("Score", "@ys"),
                ("Planner", "@planners"),
                ("Experiment", "@experiments"),
                ("Aggregator", "@aggregators"),
            ]
        )
        number_of_figures = ceil(len(metric_statistic_names) / self._number_metrics_per_figure)

        # Create figures based on the number of metrics per figure
        scenario_metric_score_figures: Dict[str, Figure] = defaultdict()
        for index in range(number_of_figures):
            starting_index = index * self._number_metrics_per_figure
            ending_index = starting_index + self._number_metrics_per_figure
            selected_metric_names = metric_statistic_names[starting_index:ending_index]
            scenario_metric_score_figure = self._render_scalar_figure(
                title="",
                y_axis_label="score",
                hover=hover,
                x_range=selected_metric_names,
                sizes=self._scenario_metric_score_data_figure_sizes,
            )

            # Plot scatter on the figure
            metric_score_data = {metric_name: data[metric_name] for metric_name in selected_metric_names}
            self._render_scenario_metric_score_scatter(
                scatter_figure=scenario_metric_score_figure, scenario_metric_score_data=metric_score_data
            )
            scenario_metric_score_figures[str(index)] = scenario_metric_score_figure
        return scenario_metric_score_figures

    def _render_grid_plot(self, figures: Dict[str, Figure], plot_width: int, legend: bool = True) -> LayoutDOM:
        """
        Render a grid plot.
        :param figures: A dict of figure names and figures.
        :param plot_width: Width of each plot.
        :param legend: If figures have legends.
        :return A grid plot.
        """
        figure_plot_list: List[Figure] = []
        for figure_name, figure_plot in figures.items():
            if legend:
                figure_plot.legend.label_text_font_size = scenario_tab_style["plot_legend_label_text_font_size"]
                figure_plot.legend.background_fill_alpha = 0.0
            figure_plot_list.append(figure_plot)

        grid_plot = gridplot(figure_plot_list, ncols=self.get_plot_cols(plot_width=plot_width), toolbar_location="left")
        return grid_plot

    def _render_scenario_metric_layout(
        self, figure_data: Dict[str, Figure], default_div: Div, plot_width: int, legend: bool = True
    ) -> column:
        """
        Render a layout for scenario metric.
        :param figure_data: A dict of figure_data.
        :param default_div: Default message when there is no result.
        :param plot_width: Figure width.
        :param legend: If figures have legends.
        :return A bokeh column layout.
        """
        if not figure_data:
            return column(self._default_time_series_div)

        grid_plot = self._render_grid_plot(figures=figure_data, plot_width=plot_width, legend=legend)
        scenario_metric_layout = column(grid_plot)
        return scenario_metric_layout

    def _render_simulations(self) -> column:
        """
        Render simulation plot.
        :return: A list of Bokeh columns or rows.
        """
        selected_keys = [
            key
            for key in self.experiment_file_data.simulation_scenario_keys
            if key.scenario_type == self._scalar_scenario_type_select.value
            and key.log_name == self._scalar_log_name_select.value
            and key.scenario_name == self._scalar_scenario_name_select.value
            and key.nuboard_file_index in self._experiment_file_active_index
        ]
        if not selected_keys:
            simulation_layouts = column(self._default_simulation_div)
        else:
            self._simulation_figure_data = self.simulation_tile.render_simulation_tiles(
                selected_scenario_keys=selected_keys, figure_sizes=self.simulation_figure_sizes
            )
            simulation_figures = [data.plot for data in self._simulation_figure_data]
            simulation_layouts = gridplot(
                simulation_figures,
                ncols=self.get_plot_cols(plot_width=self.simulation_figure_sizes[0]),
                toolbar_location=None,
            )

        return simulation_layouts
