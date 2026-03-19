package com.skala.fab.engine;

public interface SimulationEngine {
    EngineSnapshot reset();
    EngineSnapshot pause();
    EngineSnapshot resume();
    EngineSnapshot step(int actionIndex);
    EngineSnapshot status();
}
