package com.skala.fab.engine;

import java.util.List;

public record EngineSnapshot(
    double simTime,
    boolean paused,
    boolean done,
    List<LotState> activeLots
) {}
