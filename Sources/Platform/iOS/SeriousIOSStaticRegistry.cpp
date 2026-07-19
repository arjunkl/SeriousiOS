#include "SeriousIOSStaticRegistry.h"

namespace seriousios {

StaticSymbolRegistry& StaticSymbolRegistry::shared() noexcept {
    static StaticSymbolRegistry registry;
    return registry;
}

bool StaticSymbolRegistry::registerSymbol(const char* name, void* address) noexcept {
    if (name == nullptr || *name == '\0' || address == nullptr) {
        return false;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    const std::pair<std::unordered_map<std::string, void*>::iterator, bool> result =
        symbols_.emplace(name, address);
    return result.second || result.first->second == address;
}

void* StaticSymbolRegistry::findSymbol(const char* name) const noexcept {
    if (name == nullptr || *name == '\0') {
        return nullptr;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    const std::unordered_map<std::string, void*>::const_iterator iterator = symbols_.find(name);
    return iterator == symbols_.end() ? nullptr : iterator->second;
}

std::size_t StaticSymbolRegistry::size() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return symbols_.size();
}

void StaticSymbolRegistry::clearForTests() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    symbols_.clear();
}

} // namespace seriousios

extern "C" bool SeriousIOS_RegisterStaticSymbol(const char* name, void* address) noexcept {
    return seriousios::StaticSymbolRegistry::shared().registerSymbol(name, address);
}

extern "C" void* SeriousIOS_FindStaticSymbol(const char* name) noexcept {
    return seriousios::StaticSymbolRegistry::shared().findSymbol(name);
}

extern "C" std::size_t SeriousIOS_StaticSymbolCount() noexcept {
    return seriousios::StaticSymbolRegistry::shared().size();
}
