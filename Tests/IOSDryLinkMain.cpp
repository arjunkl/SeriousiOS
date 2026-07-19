#include <cstddef>

#if defined(SERIOUSIOS_TFE)
extern "C" bool SeriousIOS_TFE_RegisterEntitySymbols() noexcept;
extern "C" bool SeriousIOS_TFE_RegisterRuntimeSymbols() noexcept;
extern "C" std::size_t SeriousIOS_TFE_EntitySymbolCount() noexcept;
extern "C" std::size_t SeriousIOS_TFE_RuntimeSymbolCount() noexcept;
#define SERIOUSIOS_REGISTER_ENTITIES SeriousIOS_TFE_RegisterEntitySymbols
#define SERIOUSIOS_REGISTER_RUNTIME SeriousIOS_TFE_RegisterRuntimeSymbols
#define SERIOUSIOS_ENTITY_COUNT SeriousIOS_TFE_EntitySymbolCount
#define SERIOUSIOS_RUNTIME_COUNT SeriousIOS_TFE_RuntimeSymbolCount
#elif defined(SERIOUSIOS_TSE)
extern "C" bool SeriousIOS_TSE_RegisterEntitySymbols() noexcept;
extern "C" bool SeriousIOS_TSE_RegisterRuntimeSymbols() noexcept;
extern "C" std::size_t SeriousIOS_TSE_EntitySymbolCount() noexcept;
extern "C" std::size_t SeriousIOS_TSE_RuntimeSymbolCount() noexcept;
#define SERIOUSIOS_REGISTER_ENTITIES SeriousIOS_TSE_RegisterEntitySymbols
#define SERIOUSIOS_REGISTER_RUNTIME SeriousIOS_TSE_RegisterRuntimeSymbols
#define SERIOUSIOS_ENTITY_COUNT SeriousIOS_TSE_EntitySymbolCount
#define SERIOUSIOS_RUNTIME_COUNT SeriousIOS_TSE_RuntimeSymbolCount
#else
#error "Define SERIOUSIOS_TFE or SERIOUSIOS_TSE"
#endif

extern "C" std::size_t SeriousIOS_StaticSymbolCount() noexcept;

int main() {
    const bool entitiesRegistered = SERIOUSIOS_REGISTER_ENTITIES();
    const bool runtimeRegistered = SERIOUSIOS_REGISTER_RUNTIME();
    const std::size_t expected = SERIOUSIOS_ENTITY_COUNT() + SERIOUSIOS_RUNTIME_COUNT();
    const bool complete = SeriousIOS_StaticSymbolCount() == expected;
    return entitiesRegistered && runtimeRegistered && complete ? 0 : 1;
}
