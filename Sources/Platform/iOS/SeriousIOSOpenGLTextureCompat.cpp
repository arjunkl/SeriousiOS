#include "SeriousIOSDiagnostics.h"
#include "SeriousIOSPlatformBridge.h"

#include <OpenGLES/ES1/gl.h>
#include <OpenGLES/ES1/glext.h>

#include <atomic>
#include <cstring>
#include <type_traits>

namespace {

constexpr GLenum kLegacyClamp = 0x2900;
constexpr GLenum kTextureMaxAnisotropy = 0x84FE;

std::atomic<GLenum> gPendingError{GL_NO_ERROR};

template <typename Function>
void* functionAddress(Function function) {
    static_assert(std::is_pointer<Function>::value, "function pointer required");
    static_assert(sizeof(Function) == sizeof(void*), "unexpected function pointer size");
    void* address = nullptr;
    std::memcpy(&address, &function, sizeof(address));
    return address;
}

bool extensionListContains(const char* extensions, const char* extension) {
    if (extensions == nullptr || extension == nullptr || *extension == '\0') {
        return false;
    }

    const size_t length = std::strlen(extension);
    const char* match = extensions;
    while ((match = std::strstr(match, extension)) != nullptr) {
        const bool startsAtBoundary = match == extensions || match[-1] == ' ';
        const char after = match[length];
        const bool endsAtBoundary = after == '\0' || after == ' ';
        if (startsAtBoundary && endsAtBoundary) {
            return true;
        }
        match += length;
    }
    return false;
}

bool supportsAnisotropy() {
    const GLubyte* extensions = glGetString(GL_EXTENSIONS);
    return extensionListContains(
        reinterpret_cast<const char*>(extensions),
        "GL_EXT_texture_filter_anisotropic");
}

GLint normalizedInternalFormat(GLenum externalFormat) {
    // OpenGL ES 1.1 requires the unsized internal format to match the
    // external format. Serious Engine Classic selects desktop-sized formats
    // such as GL_RGBA8, GL_RGB5_A1, and GL_LUMINANCE8_ALPHA8. The source data
    // format is the authoritative representation for ES1.
    switch (externalFormat) {
        case GL_ALPHA:
        case GL_LUMINANCE:
        case GL_LUMINANCE_ALPHA:
        case GL_RGB:
        case GL_RGBA:
            return static_cast<GLint>(externalFormat);
#ifdef GL_BGRA
        case GL_BGRA:
            return GL_RGBA;
#endif
        default:
            return static_cast<GLint>(externalFormat);
    }
}

GLenum captureError() {
    const GLenum error = glGetError();
    if (error != GL_NO_ERROR) {
        GLenum expected = GL_NO_ERROR;
        gPendingError.compare_exchange_strong(
            expected,
            error,
            std::memory_order_release,
            std::memory_order_relaxed);
    }
    return error;
}

GLenum seriousIOSGetError() {
    const GLenum pending = gPendingError.exchange(
        GL_NO_ERROR,
        std::memory_order_acq_rel);
    return pending != GL_NO_ERROR ? pending : glGetError();
}

void seriousIOSTexImage2D(
    GLenum target,
    GLint level,
    GLint internalFormat,
    GLsizei width,
    GLsizei height,
    GLint border,
    GLenum format,
    GLenum type,
    const GLvoid* pixels) {
    const GLint normalized = normalizedInternalFormat(format);
    glTexImage2D(
        target,
        level,
        normalized,
        width,
        height,
        border,
        format,
        type,
        pixels);
    const GLenum error = captureError();
    SeriousIOS_DiagnosticsRecordTextureUpload(
        static_cast<uint32_t>(internalFormat),
        static_cast<uint32_t>(normalized),
        width,
        height,
        level,
        static_cast<uint32_t>(error));
}

void seriousIOSTexParameteri(GLenum target, GLenum parameter, GLint value) {
    const GLint requested = value;
    if (target == GL_TEXTURE_2D
        && (parameter == GL_TEXTURE_WRAP_S || parameter == GL_TEXTURE_WRAP_T)
        && static_cast<GLenum>(value) == kLegacyClamp) {
        value = GL_CLAMP_TO_EDGE;
    }

    if (parameter == kTextureMaxAnisotropy && !supportsAnisotropy()) {
        SeriousIOS_DiagnosticsLog(
            "texture",
            "ignored_unsupported_anisotropy value=%d",
            value);
        return;
    }

    glTexParameteri(target, parameter, value);
    const GLenum error = captureError();
    if (requested != value || error != GL_NO_ERROR) {
        SeriousIOS_DiagnosticsRecordTextureParameterNormalization(
            static_cast<uint32_t>(parameter),
            requested,
            value,
            static_cast<uint32_t>(error));
    }
}

void seriousIOSTexParameterf(GLenum target, GLenum parameter, GLfloat value) {
    const GLfloat requested = value;
    if (target == GL_TEXTURE_2D
        && (parameter == GL_TEXTURE_WRAP_S || parameter == GL_TEXTURE_WRAP_T)
        && static_cast<GLenum>(value) == kLegacyClamp) {
        value = static_cast<GLfloat>(GL_CLAMP_TO_EDGE);
    }

    if (parameter == kTextureMaxAnisotropy && !supportsAnisotropy()) {
        SeriousIOS_DiagnosticsLog(
            "texture",
            "ignored_unsupported_anisotropy value=%g",
            static_cast<double>(value));
        return;
    }

    glTexParameterf(target, parameter, value);
    const GLenum error = captureError();
    if (requested != value || error != GL_NO_ERROR) {
        SeriousIOS_DiagnosticsRecordTextureParameterNormalization(
            static_cast<uint32_t>(parameter),
            static_cast<int>(requested),
            static_cast<int>(value),
            static_cast<uint32_t>(error));
    }
}

} // namespace

extern "C" void* SeriousIOS_GetOpenGLTextureCompatProcAddress(
    const char* procedure) {
    if (procedure == nullptr || *procedure == '\0') {
        return nullptr;
    }
    if (std::strcmp(procedure, "glGetError") == 0) {
        return functionAddress(&seriousIOSGetError);
    }
    if (std::strcmp(procedure, "glTexImage2D") == 0) {
        return functionAddress(&seriousIOSTexImage2D);
    }
    if (std::strcmp(procedure, "glTexParameteri") == 0) {
        return functionAddress(&seriousIOSTexParameteri);
    }
    if (std::strcmp(procedure, "glTexParameterf") == 0) {
        return functionAddress(&seriousIOSTexParameterf);
    }
    return nullptr;
}
