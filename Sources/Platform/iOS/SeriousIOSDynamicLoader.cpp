#include <Engine/Engine.h>
#include <Engine/Base/DynamicLoader.h>

#include "SeriousIOSStaticRegistry.h"

namespace {

class CSeriousIOSDynamicLoader final : public CDynamicLoader {
public:
    explicit CSeriousIOSDynamicLoader(const char* libraryName)
        : libraryName_(libraryName != nullptr ? libraryName : "<main>") {}

    void* FindSymbol(const char* symbol) override {
        void* address = SeriousIOS_FindStaticSymbol(symbol);
        if (address != nullptr) {
            error_ = "";
            return address;
        }

        error_.PrintF(
            "SeriousiOS static symbol '%s' is not registered for module '%s'",
            symbol != nullptr ? symbol : "<null>",
            (const char*)libraryName_);
        return nullptr;
    }

    const char* GetError() override {
        return error_.Length() > 0 ? (const char*)error_ : nullptr;
    }

private:
    CTString libraryName_;
    CTString error_;
};

} // namespace

CDynamicLoader* CDynamicLoader::GetInstance(const char* libraryName) {
    return new CSeriousIOSDynamicLoader(libraryName);
}

CTFileName CDynamicLoader::ConvertLibNameToPlatform(const char* libraryName) {
    // Serialized package names remain intact for compatibility, but no file is
    // loaded on iOS. Symbol resolution is handled by SeriousIOSStaticRegistry.
    return CTString(libraryName != nullptr ? libraryName : "");
}
