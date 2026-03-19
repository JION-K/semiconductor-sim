package com.skala.fab.engine;

public record LotState(
    String lotName,
    String routeId,
    int remSteps,
    int totalSteps,
    String status
) {}
