FC = FC or {}
FC.version = "0.1.0"
FC.runtime = nil
FC.quality = "high"
FC.wetness = 0.0
FC.night = 0.0
FC.debug = false

function FC.log(message, level)
    outputDebugString("[Northpoint Harbor] " .. tostring(message), level or 3)
end

addEventHandler("onClientResourceStart", resourceRoot, function()
    FC.log("resource started; static city geometry is loaded as tile-based high/low LOD objects")
    if FC.loadCity then
        FC.loadCity()
    end
    if FC.startEnvironment then
        FC.startEnvironment()
    end
end)

addEventHandler("onClientResourceStop", resourceRoot, function()
    if FC.stopEnvironment then
        FC.stopEnvironment()
    end
    if FC.unloadCity then
        FC.unloadCity()
    end
end)
