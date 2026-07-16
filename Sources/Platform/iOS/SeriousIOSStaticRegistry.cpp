#include "SeriousIOSStaticRegistry.h"

namespace seriousios {

StaticSymbolRegistry& StaticSymbolRegistry::shared() noexcept {
    static StaticSymbolRegistry registry;
    return registry;
}

bool StaticSymbolRegistry::registerSymbol(std::string_view name, void* address) noexcept {
    if (name.empty() || address == nullptr) {
        return false;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    auto [iterator, inserted] = symbols_.emplace(std::string(name), address);
    return inserted || iterator->second == address;
}

void* StaticSymbolRegistry::findSymbol(std::string_view name) const noexcept {
    if (name.empty()) {
        return nullptr;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    const auto iterator = symbols_.find(std::string(name));
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
    return name != nullptr && seriousios::StaticSymbolRegistry::shared().registerSymbol(name, address);
}

extern "C" void* SeriousIOS_FindStaticSymbol(const char* name) noexcept {
    return name == nullptr ? nullptr : seriousios::StaticSymbolRegistry::shared().findSymbol(name);
}

extern "C" std::size_t SeriousIOS_StaticSymbolCount() noexcept {
    return seriousios::StaticSymbolRegistry::shared().size();
}
