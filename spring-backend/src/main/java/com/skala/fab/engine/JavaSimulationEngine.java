package com.skala.fab.engine;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * Stage 3 skeleton:
 * SimPy parity replacement point.
 */
@Component
@Profile("java-engine")
public class JavaSimulationEngine implements SimulationEngine {
    private double simTime = 0.0;
    private boolean paused = true;
    private boolean done = false;
    private final List<LotState> activeLots = new ArrayList<>();

    @Override
    public EngineSnapshot reset() {
        simTime = 0.0;
        paused = true;
        done = false;
        activeLots.clear();
        activeLots.add(new LotState("Lot_Product_3_1", "Route_Product_E3", 583, 583, "Queuing"));
        activeLots.add(new LotState("Lot_Product_4_1", "Route_Product_E4", 343, 343, "Queuing"));
        return status();
    }

    @Override
    public EngineSnapshot pause() {
        paused = true;
        return status();
    }

    @Override
    public EngineSnapshot resume() {
        paused = false;
        return status();
    }

    @Override
    public EngineSnapshot step(int actionIndex) {
        if (done || paused) {
            return status();
        }
        simTime += 1.0;
        if (!activeLots.isEmpty()) {
            LotState l = activeLots.get(0);
            int next = Math.max(0, l.remSteps() - 1);
            activeLots.set(0, new LotState(l.lotName(), l.routeId(), next, l.totalSteps(), "Processing"));
        }
        return status();
    }

    @Override
    public EngineSnapshot status() {
        return new EngineSnapshot(simTime, paused, done, List.copyOf(activeLots));
    }
}
