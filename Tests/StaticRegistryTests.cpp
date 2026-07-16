#include "SeriousIOSStaticRegistry.h"

#include <cassert>
#include <cstdint>
#include <string>
#include <thread>
#include <vector>

namespace {

int firstSymbol = 1;
int secondSymbol = 2;
int conflictingSymbol = 3;

} // namespace

int main() {
    seriousios::StaticSymbolRegistry& registry = seriousios::StaticSymbolRegistry::shared();
    registry.clearForTests();

    assert(registry.size() == 0);
    assert(!registry.registerSymbol("", &firstSymbol));
    assert(!registry.registerSymbol("Null", nullptr));

    assert(registry.registerSymbol("Player_DLLClass", &firstSymbol));
    assert(registry.registerSymbol("Player_DLLClass", &firstSymbol));
    assert(!registry.registerSymbol("Player_DLLClass", &conflictingSymbol));
    assert(registry.findSymbol("Player_DLLClass") == &firstSymbol);
    assert(registry.findSymbol("Missing") == nullptr);

    assert(SeriousIOS_RegisterStaticSymbol("Game_Startup", &secondSymbol));
    assert(SeriousIOS_FindStaticSymbol("Game_Startup") == &secondSymbol);
    assert(SeriousIOS_StaticSymbolCount() == 2);

    std::vector<std::thread> workers;
    for (std::uintptr_t index = 0; index < 16; ++index) {
        workers.emplace_back([index, &registry] {
            const std::string name = "Concurrent_" + std::to_string(index);
            void* address = reinterpret_cast<void*>(index + 1);
            assert(registry.registerSymbol(name.c_str(), address));
            assert(registry.findSymbol(name.c_str()) == address);
        });
    }
    for (std::vector<std::thread>::iterator worker = workers.begin(); worker != workers.end(); ++worker) {
        worker->join();
    }

    assert(registry.size() == 18);
    registry.clearForTests();
    assert(registry.size() == 0);
    return 0;
}
