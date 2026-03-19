package com.skala.fab.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.skala.fab.dto.DispatchRequest;
import com.skala.fab.dto.StatusResponse;
import com.skala.fab.dto.UiEventRequest;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
public class SimulationFacadeService {
    private final PythonEngineClient engineClient;
    private final ObjectMapper objectMapper;

    public SimulationFacadeService(PythonEngineClient engineClient, ObjectMapper objectMapper) {
        this.engineClient = engineClient;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> root() {
        return asMap(engineClient.get("/"));
    }

    public StatusResponse status() {
        return objectMapper.convertValue(engineClient.get("/api/status"), StatusResponse.class);
    }

    public StatusResponse step() {
        return objectMapper.convertValue(engineClient.post("/api/step"), StatusResponse.class);
    }

    public StatusResponse reset() {
        return objectMapper.convertValue(engineClient.post("/api/control/reset"), StatusResponse.class);
    }

    public StatusResponse pause() {
        return objectMapper.convertValue(engineClient.post("/api/control/pause"), StatusResponse.class);
    }

    public StatusResponse resume() {
        return objectMapper.convertValue(engineClient.post("/api/control/resume"), StatusResponse.class);
    }

    public StatusResponse dispatch(DispatchRequest request) {
        JsonNode node = engineClient.post("/api/dispatch", Map.of("action_idx", request.action_idx()));
        return objectMapper.convertValue(node, StatusResponse.class);
    }

    public Map<String, Object> layout() {
        return asMap(engineClient.get("/api/layout"));
    }

    public Map<String, Object> uiEvent(UiEventRequest request) {
        JsonNode node = engineClient.post(
            "/api/debug/ui-event",
            Map.of(
                "event", request.event(),
                "details", request.details() == null ? Map.of() : request.details()
            )
        );
        return asMap(node);
    }

    public Map<String, Object> fileWriteCheck() {
        return asMap(engineClient.get("/api/debug/file-write-check"));
    }

    private Map<String, Object> asMap(JsonNode node) {
        return objectMapper.convertValue(node, new TypeReference<>() {});
    }
}
