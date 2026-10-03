FC = FC or {}

local function readRuntimeFile()
    local file = fileOpen("data/city_runtime.json")
    if not file then
        FC.log("cannot open data/city_runtime.json; run tools/build_city.py first", 1)
        return false
    end
    local raw = fileRead(file, fileGetSize(file))
    fileClose(file)
    local value = raw and fromJSON(raw)
    if type(value) ~= "table" then
        FC.log("runtime JSON is invalid", 1)
        return false
    end
    return value
end

local function loadModel(dffPath, modelID)
    local dff = engineLoadDFF(dffPath)
    if not dff then
        FC.log("engineLoadDFF failed: " .. tostring(dffPath), 1)
        return false
    end
    local replaced = engineReplaceModel(dff, modelID, true)
    if not replaced then
        FC.log("engineReplaceModel failed for " .. tostring(dffPath), 1)
        destroyElement(dff)
        return false
    end
    -- Keep the DFF element alive: destroying it resets the replacement model.
    FC.loadedModels[#FC.loadedModels + 1] = dff
    return true
end

function FC.loadCity()
    if FC.runtime then
        return true
    end
    local runtime = readRuntimeFile()
    if not runtime then
        return false
    end
    FC.runtime = runtime
    FC.tiles = {}
    FC.modelIDs = {}
    FC.loadedModels = {}
    FC.loadedCOLs = {}
    FC.loadedTextures = {}

    -- Load collision first; MTA's model pipeline expects COL -> TXD -> DFF.
    for _, tile in ipairs(runtime.tiles or {}) do
        local highID = engineRequestModel("object")
        if not highID then
            FC.log("engineRequestModel ran out of custom object IDs", 1)
            break
        end
        FC.modelIDs[#FC.modelIDs + 1] = highID
        local lowID = engineRequestModel("object")
        if not lowID then
            FC.log("engineRequestModel ran out of custom object IDs", 1)
            break
        end
        FC.modelIDs[#FC.modelIDs + 1] = lowID
        tile.highModelID = highID
        tile.lowModelID = lowID

        if tile.col then
            local col = engineLoadCOL(tile.col)
            if col then
                if engineReplaceCOL(col, highID) then
                    FC.loadedCOLs[#FC.loadedCOLs + 1] = col
                else
                    FC.log("engineReplaceCOL failed: " .. tostring(tile.col), 2)
                    destroyElement(col)
                end
            else
                FC.log("engineLoadCOL failed: " .. tostring(tile.col), 2)
            end
        end
    end

    local txd = engineLoadTXD("textures/fc_materials.txd", false)
    if not txd then
        FC.log("engineLoadTXD failed: textures/fc_materials.txd", 1)
        FC.unloadCity()
        FC.runtime = nil
        return false
    end
    FC.txd = txd

    for _, tile in ipairs(runtime.tiles or {}) do
        local highID, lowID = tile.highModelID, tile.lowModelID
        if highID and lowID then
            engineImportTXD(txd, highID)
            engineImportTXD(txd, lowID)
            local highOK = loadModel(tile.highDff, highID)
            local lowOK = loadModel(tile.lowDff, lowID)
            if highOK and lowOK then
                engineSetModelLODDistance(highID, runtime.lodHighDistance or 165, true)
                engineSetModelLODDistance(lowID, runtime.lodFarDistance or 500, true)
                local x, y, z = tonumber(tile.worldX), tonumber(tile.worldY), tonumber(tile.worldZ) or 0
                local high = createObject(highID, x, y, z, 0, 0, 0, false, false)
                local low = createObject(lowID, x, y, z, 0, 0, 0, true, false)
                if high and low then
                    setElementFrozen(high, true)
                    setElementFrozen(low, true)
                    setElementCollisionsEnabled(low, false)
                    setLowLODElement(high, low)
                    FC.tiles[#FC.tiles + 1] = {high = high, low = low, record = tile}
                else
                    if isElement(high) then destroyElement(high) end
                    if isElement(low) then destroyElement(low) end
                    FC.log("createObject failed for tile " .. tostring(tile.id), 1)
                end
            end
        end
    end

    if FC.createShaders then
        FC.createShaders()
    end
    if FC.applyShadersToTile then
        for _, tile in ipairs(FC.tiles) do
            FC.applyShadersToTile(tile)
        end
    end
    if FC.applyQuality then
        FC.applyQuality(FC.quality)
    end
    FC.log("loaded " .. tostring(#FC.tiles) .. " streamed terrain/city tiles")
    return true
end

function FC.unloadCity()
    for _, tile in ipairs(FC.tiles or {}) do
        if isElement(tile.high) then destroyElement(tile.high) end
        if isElement(tile.low) then destroyElement(tile.low) end
    end
    FC.tiles = {}
    for _, dff in ipairs(FC.loadedModels or {}) do
        if isElement(dff) then destroyElement(dff) end
    end
    FC.loadedModels = {}
    for _, col in ipairs(FC.loadedCOLs or {}) do
        if isElement(col) then destroyElement(col) end
    end
    FC.loadedCOLs = {}
    for _, modelID in ipairs(FC.modelIDs or {}) do
        engineFreeModel(modelID)
    end
    FC.modelIDs = {}
    for _, element in ipairs(FC.loadedTextures or {}) do
        if isElement(element) then destroyElement(element) end
    end
    FC.loadedTextures = {}
    if isElement(FC.txd) then destroyElement(FC.txd) end
    FC.txd = nil
    FC.runtime = nil
end
