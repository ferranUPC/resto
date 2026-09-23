# Request bank — variant review

24 variants, 23 LLM-generated, 2 failed verification, total cost $0.0027.

Review every **FAIL** and every **SAMPLE**; fix a variant by editing its `text` in `variants.json`.

## R001 · single · dev

> On the DEV-NET network, what would happen to the mean travel time if lane 1 of edge B0C0 were closed from 08:00 to 08:30?

Gold: intent `counterfactual` · network `DEV-NET` · 1 arm(s): treatment · metrics mean_travel_time

### `R001.ca` — ok

- text: A la xarxa DEV-NET, què passaria amb el temps de viatge mitjà si es tanqués el carril 1 de l'aresta B0C0 des de les 08:00 fins a les 08:30?
- back-translation: To the DEV-NET network, what would happen to the average travel time if lane 1 of edge B0C0 were closed from 08:00 to 08:30?

### `R001.es` — ok

- text: En la red DEV-NET, ¿qué ocurriría con el tiempo medio de viaje si se cerrara el carril 1 del enlace B0C0 desde las 08:00 hasta las 08:30?
- back-translation: In the DEV-NET network, what would happen to the mean travel time if lane 1 of link B0C0 were closed from 08:00 to 08:30?

### `R001.de` — ok

- text: Auf dem DEV-NET-Netzwerk: Was würde mit der mittleren Reisezeit passieren, wenn die Fahrspur 1 der Kante B0C0 von 08:00 bis 08:30 gesperrt wäre?
- back-translation: On the DEV-NET network: What would happen to the median travel time if lane 1 of edge B0C0 were closed from 08:00 to 08:30?

### `R001.zh` — ok

- text: 在 DEV-NET 网络上，如果将边 B0C0 的车道 1 在 08:00 至 08:30 期间关闭，平均行程时间会发生什么变化？
- back-translation: On the DEV-NET network, if lane 1 of edge B0C0 is closed between 08:00 and 08:30, what happens to the average travel time?

### `R001.en-colloquial` — ok

- text: Hey, on the DEV-NET network, if I close lane 1 of edge B0C0 from 8 to 8:30, what happens to the mean travel time?

### `R001.en-telegraphic` — ok

- text: DEV-NET: mean travel time if edge B0C0 lane 1 closed 08:00–08:30?

### `R001.es-vague_time` — ok

- text: En la red DEV-NET, ¿qué ocurriría con el tiempo medio de viaje si se cerrara el carril 1 del borde B0C0 por la mañana temprano durante un rato?
- back-translation: In the DEV-NET network, what would happen to the mean travel time if lane 1 of edge B0C0 were closed early in the morning for a while?
- verifier: time specification

### `R001.en-typos` — ok

- text: On the DEV-NET network, what would happen to the mean travel time if lane 1 of ege B0C0 were closed fom 08:00 to 08:30?

## R002 · single · dev

> During the morning peak on DEV-NET, which edges have the highest occupancy?

Gold: intent `describe` · network `DEV-NET` · demand `peak` · metrics occupancy

### `R002.ca` — FAIL

- text: Durant el matí de punta a DEV-NET, quins vèrtexs tenen la major ocupació?
- back-translation: During the morning peak on DEV-NET, which vertices have the highest occupancy?
- verifier: unparseable verifier output

### `R002.zh` — ok

- text: 在 DEV-NET 的早高峰期间，哪些路段的占用率最高？
- back-translation: During the morning peak hours on DEV-NET, which road segments have the highest occupancy rates?

### `R002.en-messy` — ok

- text: URGENT! morning peak on DEV-NET, which edges highest occupancy? need stats ASAP!

### `R002.es-no_accents` — ok

- text: Durante la hora punta de la manana en DEV-NET, ¿que aristas tienen la mayor ocupacion?
- back-translation: During the morning peak hour on DEV-NET, which edges have the highest occupancy?

## R003 · multi_arm · dev

> On DEV-NET, which reduces the mean delay more: closing edge C0D0 from 08:00 to 08:30, or limiting edge B2C2 to 30 km/h over the same period?

Gold: intent `compare` · network `DEV-NET` · 2 arm(s): closure; speed_limit · metrics mean_delay

### `R003.ca` — ok

- text: A DEV-NET, què redueix més el retard mitjà: tancar l'aresta C0D0 de 08:00 a 08:30, o limitar l'aresta B2C2 a 30 km/h durant el mateix període?
- back-translation: A DEV-NET, which reduces the average delay more: closing the edge C0D0 from 08:00 to 08:30, or limiting the edge B2C2 to 30 km/h during the same period?

### `R003.de` — ok

- text: Auf DEV-NET: Was verringert die mittene Verzögerung mehr: das Schließen der Kante C0D0 von 08:00 bis 08:30 oder die Begrenzung der Kante B2C2 auf 30 km/h im selben Zeitraum?
- back-translation: On DEV-NET: What reduces the median latency more: closing edge C0D0 from 08:00 to 08:30, or limiting edge B2C2 to 30 km/h in the same period?

### `R003.zh` — ok

- text: 在 DEV-NET 上，从 08:00 到 08:30 关闭边 C0D0，与在同一时段内将边 B2C2 限速至 30 km/h，哪一种更能降低平均延迟？
- back-translation: On DEV-NET, between 08:00 and 08:30, which reduces average latency more: closing edge C0D0 or limiting the speed of edge B2C2 to 30 km/h during the same period?

### `R003.en-verbose` — ok

- text: I am a traffic analyst currently working on a comparative study for the DEV-NET simulation environment, and I need to verify the impact of specific congestion management strategies during the morning rush hour. My goal is to determine which intervention yields a greater reduction in the mean delay across the network. Specifically, I am asking: on DEV-NET, which reduces the mean delay more: closing edge C0D0 from 08:00 to 08:30, or limiting edge B2C2 to 30 km/h over the same period? Please ensure the comparison is strictly between these two scenarios within the defined timeframe.

### `R003.en-vague_grouping` — FAIL

- text: On DEV-NET, closing edge C0D0 from 08:00 to 08:30 reduces the mean delay. Limiting edge B2C2 to 30 km/h over the same period also reduces the mean delay.
- verifier: comparison vs application of changes
- verifier: question type

## R004 · combined · dev

> Run a simulation of DEV-NET in which lane 1 of B0C0 is closed and edge B2C2 is limited to 30 km/h at the same time, both from 08:00 to 08:30, and report the mean delay.

Gold: intent `run` · network `DEV-NET` · 1 arm(s): treatment · metrics mean_delay

### `R004.es` — ok

- text: Ejecuta una simulación de DEV-NET en la que la carril 1 de B0C0 esté cerrado y el borde B2C2 esté limitado a 30 km/h simultáneamente, ambos desde las 08:00 hasta las 08:30, e informa el retraso medio.
- back-translation: Run a DEV-NET simulation in which lane 1 of B0C0 is closed and the edge B2C2 is limited to 30 km/h simultaneously, both from 08:00 to 08:30, and report the average delay.

### `R004.zh` — ok

- text: 在 DEV-NET 中运行一次模拟，同时关闭 B0C0 的 1 号车道并将 B2C2 边缘限速为 30 km/h，时间范围均为 08:00 至 08:30，并报告平均延误。
- back-translation: Run a simulation in DEV-NET, while closing lane 1 of B0C0 and setting the speed limit on the B2C2 edge to 30 km/h, for the time range 08:00 to 08:30, and report the average delay.

### `R004.en-telegraphic` — ok

- text: DEV-NET sim: B0C0 lane 1 closed, B2C2 edge 30 km/h, 08:00–08:30. Report mean delay.

### `R004.de-typos` — ok

- text: Führe eine Simulation von DEV-NET drch, bei der Fahrspur 1 von B0C0 gesperrt und Kante B2C2 gleichzeeitig auf 30 km/h begrenzt ist, beide von 08:00 bis 08:30, und gib die mittlere Verzögerung an.
- back-translation: Run a simulation of DEV-NET in which lane 1 of B0C0 is blocked and edge B2C2 is simultaneously limited to 30 km/h, both from 08:00 to 08:30, and provide the average delay.

## R005 · ambiguous · dev

> What happens if I close B0C0 and C0D0?

Gold: expect `ambiguities[]` (together or separately, and when)

### `R005.ca` — ok

- text: Què passa si tanc B0C0 i C0D0?
- back-translation: What happens if you close B0C0 and C0D0?

### `R005.zh` — ok

- text: 如果我关闭 B0C0 和 C0D0，会发生什么？
- back-translation: What happens if I turn off B0C0 and C0D0?

### `R005.en-colloquial` — ok

- text: What happens if I close the edge from B0 to C0 and the one from C0 to D0?

