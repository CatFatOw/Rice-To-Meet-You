# Rice-To-Meet-You: UrbanTwin

## Simulating Public-Health Interventions for Mega-Events

## Inspiration

The 2026 FIFA World Cup tested cities’ ability to keep visitors and fans safe through extreme heat, crowd density, and transportation disruptions. On June 22, severe weather during Match 41 required NJ TRANSIT to activate contingency measures; across the tournament, the agency moved more than 370,000 event-related passengers through eight matches. [NJ TRANSIT source](https://www.njtransit.com/press-releases/new-jersey-interagency-transportation-after-action-report-aar-njny-stadium-fifa)

In Mexico City, four fans died following post-match celebrations, after which officials tightened crowd-capacity and security measures. [AP News source](https://apnews.com/article/mexico-world-cup-angel-zocalo-deaths-security-precautions-fe1887cada69f55d8764c96d08c59bbb)

These events highlight the need for a tool that allows city planners and officials to model weather conditions, visitor surges, and heat risk before a major event. Rice-To-Meet-You provides a map-based planning environment for evaluating a potential host city and testing interventions that improve visitor safety.

## What It Does

UrbanTwin is an interactive, map-based planning and simulation platform for major events. It combines environmental data, spatial visualization, and mathematical cooling models to support urban planners.

When first loaded, the planner sees two core options: **Explore** and **Simulation**.

### Explore Mode

In Explore mode, planners can select host cities and inspect interpolated heat-map layers for metrics such as visitor density and heat risk. They can also view key points of interest. This creates an interactive view of baseline conditions and provides context for later intervention scenarios.

### Simulation Mode

In Simulation mode, planners can explore city-level heat risk and key points of interest, select a time period, draw target areas, and place potential interventions directly on the map.

The platform models four heat-mitigation approaches:

- **Vegetation**, such as street trees, parks, green roofs, and rain gardens.
- **High-albedo surfaces**, such as cool roofs and reflective pavement.
- **Shade structures**, such as canopies, awnings, shade sails, and bus shelters.
- **Evaporative cooling**, such as fountains, splash pads, and misting systems.

Planners can drag and drop interventions onto target locations, define their area of impact, and set active dates. The platform applies weather-aware cooling models and displays resulting changes through an updated heat map and timeline. This allows planners to compare scenarios, identify high-risk areas, and prioritize practical investments that improve heat safety during future mega-events.

Together, Explore and Simulation modes allow planners to select a host city, interact with its metrics, test interventions, and understand how those interventions work within the city’s environmental conditions. The goal is to help officials identify priority areas, make data-informed investments, and prepare safer, more resilient host cities before visitors arrive.

## How We Built It

### Frontend

<span style="color:red"><strong>NEED teammate to add:</strong> Describe the React, TypeScript, MapLibre, deck.gl, and visualization implementation.</span>

### Backend

We use a FastAPI and SQLAlchemy Python-based backend organized around routers, services, and repositories. Business logic lives in service files, database querying lives in repository files, and API endpoints live in router files. The platform is backed by a live Neon-hosted PostgreSQL database.

To keep the platform responsive with large datasets and to support future multi-user scale, we combine Redis caching and preloading with Celery background workers for asynchronous processing and concurrent weather-data retrieval. This reduces repeated API calls and helps keep maps and simulations responsive.

### Machine Learning and Statistics

<span style="color:red"><strong>NEED teammate to add:</strong> Describe the machine-learning models, statistical methods, source datasets, validation, and how predictions are used in the platform.</span>

Rice-To-Meet-You simulates how urban cooling interventions change pedestrian-level temperature across a date-indexed heat map. A planner draws or places an intervention, selects when it is active, and the model recalculates map points inside its footprint, or within its cooling radius for water-based interventions.

### Ordinary Kriging Interpolation

To display continuous metric values across city grid cells, we use **Ordinary Kriging** with a linear variogram. Known metric readings estimate values at unsampled grid-cell centroids.

The predicted value at an unsampled location is:

$$
\hat{z}(s_0) = \sum_{i=1}^{n} \lambda_i z(s_i)
$$

subject to the unbiasedness constraint:

$$
\sum_{i=1}^{n} \lambda_i = 1
$$

The kriging weights are calculated by solving:

$$
\begin{bmatrix}
\gamma(s_i-s_j) & 1 \\
1^T & 0
\end{bmatrix}
\begin{bmatrix}
\lambda \\
\mu
\end{bmatrix}
=
\begin{bmatrix}
\gamma(s_i-s_0) \\
1
\end{bmatrix}
$$

The platform uses a linear variogram:

$$
\gamma(h) = \text{slope} \cdot h + \text{nugget}
$$

Where:

- $\hat{z}(s_0)$ is the predicted metric value at target centroid $s_0$.
- $z(s_i)$ is the observed value at known point $i$.
- $\lambda_i$ is the weight assigned to known point $i$.
- $\gamma(h)$ is semivariance at distance $h$.
- $\mu$ is a Lagrange multiplier enforcing unbiased interpolation.

Known grid cells keep their exact observed values; Ordinary Kriging predicts only unsampled grid-cell centroids, creating the continuous heat-map layer.

### Weather Conditions

The model calculates saturation vapor pressure:

$$
e_s(T) = 0.6108 \times e^{\frac{17.27 \times T}{T + 237.3}}
$$

It then calculates vapor-pressure deficit:

$$
VPD = e_s(T) \times \left(1 - \frac{RH}{100}\right)
$$

Where **T** is temperature in degrees Celsius and **RH** is relative humidity percentage.

### Vegetation Cooling

Vegetation combines cooling from shade and evapotranspiration.

$$
\Delta T_{\max} = 5 \times f_{VPD} \times f_{solar} \times f_{wind}
$$

$$
f_{VPD} = \min\left(\frac{VPD}{4.5}, 1\right)
$$

The leaf-area effect uses a saturating Beer–Lambert relationship:

$$
f_{LAI} = 1 - e^{-0.5 \times LAI}
$$

$$
I_{vegetation} =
0.4 \times (C \times f_{LAI} \times W)
+ 0.6 \times (C \times K \times f_{LAI} \times (0.8 + 0.2 \times W))
$$

$$
\Delta T = \Delta T_{\max} \times I_{vegetation}
$$

Where **C** is vegetation coverage, **K** is canopy fraction, **LAI** is leaf-area index, and **W** is irrigation or water availability.

### High-Albedo Surface Cooling

Reflective surfaces reduce absorbed solar energy.

$$
\Delta T_{\max} = 4 \times f_{thermal} \times f_{solar}
$$

$$
f_{thermal} =
\operatorname{clamp}\left(\frac{T - 20}{38 - 20}, 0, 1\right)
$$

$$
I_{albedo} =
\min\left(\frac{\Delta \alpha}{0.7}, 1\right) \times A
$$

Where **Δα** is albedo improvement and **A** is treated-area coverage.

### Shade-Structure Cooling

Shade structures reduce direct solar exposure.

$$
\Delta T_{\max} =
5 \times f_{thermal} \times f_{solar} \times 0.85
$$

$$
I_{shade} = O \times A
$$

Where **O** is shade opacity and **A** is shaded-footprint coverage.

### Evaporative Cooling

Water-based interventions are strongest in hot, dry conditions and diminish with distance.

$$
\Delta T_{\max} = 8 \times f_{VPD} \times f_{wind}
$$

$$
P = \left(\frac{Q}{60}\right) \times 2.45 \times 10^6
$$

$$
I_{source} = \min\left(\frac{P}{50,000}, 1\right)
$$

$$
f_{distance} = \max\left(1 - \frac{r}{R}, 0\right)
$$

$$
\Delta T =
\Delta T_{\max} \times I_{source} \times D \times f_{distance}
$$

Where **Q** is evaporation rate in liters per minute, **r** is distance from the cooling source, **R** is cooling radius, and **D** is active fraction or duty cycle.

### Diminishing-Return Simulation

When multiple interventions overlap, the simulation prevents unrealistic stacking of cooling benefits. It combines intervention effects against the same local cooling ceiling:

$$
Impact =
1 - \prod_i \left[
1 - \operatorname{clamp}\left(\frac{c_i \times F}{C}, 0, 1\right)
\right]
$$

$$
\Delta T_{combined} = C \times Impact
$$

Where **cᵢ** is an individual intervention’s cooling contribution, **C** is the local cooling ceiling, and **F** is a contextual interaction factor.

For example, vegetation and water-based cooling can reinforce one another, while vegetation and shade structures can have partially redundant benefits because both reduce solar exposure.

## Challenges

This project was ambitious. Four developers contributed around internship schedules and across Houston, Pittsburgh, and Vietnam. Below are the principal challenges and our responses.

1. **Time coordination and meetings:** We originally planned at least three meetings per week. As internships intensified and team members returned to university, availability decreased and time conflicts increased. We shifted to asynchronous communication, agile sprints, a clear task list, shared weekly meeting notes, and frequent progress reports to keep the team on track.

2. **Different technical backgrounds:** Team members had different areas of specialization, which sometimes made feature handoffs difficult. We addressed this by teaching the basics of the relevant technology and preparing short, non-technical slide presentations before major implementation discussions.

3. **Distributed development:** Parallel feature work sometimes created over- or under-engineered implementations and merge conflicts caused by overlapping changes or outdated assumptions. We improved this process through stricter testing, including unit tests, property-based tests, and GitHub integration tests, before merging work into the main codebase.

## Accomplishments That We’re Proud Of

- Built an end-to-end interactive planning prototype, combining a React map interface with a FastAPI, PostgreSQL, and Redis-backed data platform that is hosted and deployed live.
- Turned abstract heat-risk data into an accessible, grid-level visualization that helps planners explore risk at specific locations and points of interest.
- Created a simulation workspace where users can draw intervention areas and test vegetation, reflective surfaces, shade structures, and evaporative-cooling strategies modeled after environmental research and formulas.
- Made simulations weather-aware by accounting for temperature, humidity, solar exposure, wind, coverage, and intervention intensity.
- Designed for real-world scale through live database support, cached data, concurrent weather retrieval, and asynchronous background processing.
- Delivered a cohesive tool despite a distributed team working across three locations and demanding internship schedules.

## What We Learned

### Technical Challenges

- Although AI quickly reduced many technical challenges, we soon realized it provided diminishing returns as the codebase grew. As our code increased in size, complexity, and features, we quickly realized that sometimes, it became our bottleneck.
- For the backend, the biggest challenge was making code that was clean, well-documented, and scalable. Since our database was deployed on NeonDB, an online PostgreSQL provider, every time we called our API and routes, we were billed a small amount. So we had to optimize our routes and data calls and implement a Grafana dashboard to monitor usage and cost.

### Team Challenges

- The hardest part of the hackathon was not only programming or feature development. It was conveying information clearly, managing a four-person team across time zones, and keeping everyone aligned on the same goal.
- A huge challenge was working around technology constraints: database storage constraints and data-transfer/loading-speed constraints.
- <span style="color:red"><strong>NEED teammate to add:</strong> Add one or more lessons about the data, simulation design, urban-planning context, or user feedback.</span>
