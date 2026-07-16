#pragma once

#include <cstddef>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>

namespace seriousios {

// iOS cannot depend on loading game modules at runtime. This registry provides
// the symbol lookup contract that the engine's CDynamicLoader adapter will use
// after Entities, Game and Shaders are linked into the application binary.
class StaticSymbolRegistry final {
public:
    static StaticSymbolRegistry& shared() noexcept;

    // Registration is idempotent when the same symbol is registered twice.
    // A conflicting address for an existing name is rejected.
    bool registerSymbol(std::string_view name, void* address) noexcept;
    [[nodiscard]] void* findSymbol(std::string_view name) const noexcept;
    [[nodiscard]] std::size_t size() const noexcept;

    // Intended for isolated tests before engine startup only.
    void clearForTests() noexcept;

private:
    StaticSymbolRegistry() = default;

    mutable std::mutex mutex_;
    std::unordered_map<std::string, void*> symbols_;
};

} // namespace seriousios

extern "C" {

bool SeriousIOS_RegisterStaticSymbol(const char* name, void* address) noexcept;
void* SeriousIOS_FindStaticSymbol(const char* name) noexcept;
std::size_t SeriousIOS_StaticSymbolCount() noexcept;

}
