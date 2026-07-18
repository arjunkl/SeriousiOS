#include "SeriousIOSPlatformBridge.h"
#include "SeriousIOSDiagnostics.h"

#include <OpenGLES/ES1/gl.h>

#include <array>
#include <cstdio>
#include <cstring>
#include <type_traits>

namespace {

char gImmediateCompatibilityError[512] = {};

constexpr std::size_t kMaximumImmediateVertices = 4096;
constexpr std::size_t kMaximumLoggedUnsupportedModes = 8;

struct ImmediateVertex {
    GLfloat x = 0.0f;
    GLfloat y = 0.0f;
    GLfloat s = 0.0f;
    GLfloat t = 0.0f;
    GLubyte red = 0xFF;
    GLubyte green = 0xFF;
    GLubyte blue = 0xFF;
    GLubyte alpha = 0xFF;
};

struct ImmediateState {
    bool active = false;
    bool overflowed = false;
    GLenum mode = GL_LINES;
    std::size_t vertexCount = 0;
    GLfloat currentS = 0.0f;
    GLfloat currentT = 0.0f;
    GLubyte currentColor[4] = {0xFF, 0xFF, 0xFF, 0xFF};
    std::array<ImmediateVertex, kMaximumImmediateVertices> vertices = {};
};

struct ClientArrayState {
    GLint arrayBufferBinding = 0;
    GLint clientActiveTexture = GL_TEXTURE0;

    GLboolean vertexArrayEnabled = GL_FALSE;
    GLint vertexSize = 4;
    GLint vertexType = GL_FLOAT;
    GLint vertexStride = 0;
    GLvoid* vertexPointer = nullptr;

    GLboolean colorArrayEnabled = GL_FALSE;
    GLint colorSize = 4;
    GLint colorType = GL_FLOAT;
    GLint colorStride = 0;
    GLvoid* colorPointer = nullptr;

    GLboolean textureCoordinateArrayEnabled = GL_FALSE;
    GLint textureCoordinateSize = 4;
    GLint textureCoordinateType = GL_FLOAT;
    GLint textureCoordinateStride = 0;
    GLvoid* textureCoordinatePointer = nullptr;
};

thread_local ImmediateState gImmediateState;
std::array<GLenum, kMaximumLoggedUnsupportedModes> gLoggedUnsupportedModes = {};
std::size_t gLoggedUnsupportedModeCount = 0;
bool gLoggedNestedBegin = false;
bool gLoggedEndWithoutBegin = false;
bool gLoggedVertexOutsideBegin = false;
bool gImmediateModeSmokeTestPassed = false;

void logUnsupportedImmediateModeOnce(GLenum mode) {
    for (std::size_t index = 0; index < gLoggedUnsupportedModeCount; ++index) {
        if (gLoggedUnsupportedModes[index] == mode) {
            return;
        }
    }
    if (gLoggedUnsupportedModeCount < gLoggedUnsupportedModes.size()) {
        gLoggedUnsupportedModes[gLoggedUnsupportedModeCount++] = mode;
    }
    SeriousIOS_DiagnosticsLog(
        "gl-compat",
        "immediate_mode_unsupported primitive=0x%04X",
        static_cast<unsigned int>(mode));
}

bool isSupportedImmediateMode(GLenum mode) {
    switch (mode) {
        case GL_POINTS:
        case GL_LINES:
        case GL_LINE_STRIP:
        case GL_LINE_LOOP:
        case GL_TRIANGLES:
        case GL_TRIANGLE_STRIP:
        case GL_TRIANGLE_FAN:
            return true;
        default:
            return false;
    }
}

ClientArrayState captureClientArrayState() {
    ClientArrayState state;
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &state.arrayBufferBinding);
    glGetIntegerv(GL_CLIENT_ACTIVE_TEXTURE, &state.clientActiveTexture);

    glClientActiveTexture(GL_TEXTURE0);

    state.vertexArrayEnabled = glIsEnabled(GL_VERTEX_ARRAY);
    glGetIntegerv(GL_VERTEX_ARRAY_SIZE, &state.vertexSize);
    glGetIntegerv(GL_VERTEX_ARRAY_TYPE, &state.vertexType);
    glGetIntegerv(GL_VERTEX_ARRAY_STRIDE, &state.vertexStride);
    glGetPointerv(GL_VERTEX_ARRAY_POINTER, &state.vertexPointer);

    state.colorArrayEnabled = glIsEnabled(GL_COLOR_ARRAY);
    glGetIntegerv(GL_COLOR_ARRAY_SIZE, &state.colorSize);
    glGetIntegerv(GL_COLOR_ARRAY_TYPE, &state.colorType);
    glGetIntegerv(GL_COLOR_ARRAY_STRIDE, &state.colorStride);
    glGetPointerv(GL_COLOR_ARRAY_POINTER, &state.colorPointer);

    state.textureCoordinateArrayEnabled = glIsEnabled(GL_TEXTURE_COORD_ARRAY);
    glGetIntegerv(GL_TEXTURE_COORD_ARRAY_SIZE, &state.textureCoordinateSize);
    glGetIntegerv(GL_TEXTURE_COORD_ARRAY_TYPE, &state.textureCoordinateType);
    glGetIntegerv(GL_TEXTURE_COORD_ARRAY_STRIDE, &state.textureCoordinateStride);
    glGetPointerv(GL_TEXTURE_COORD_ARRAY_POINTER, &state.textureCoordinatePointer);

    return state;
}

void setClientState(GLenum array, GLboolean enabled) {
    if (enabled != GL_FALSE) {
        glEnableClientState(array);
    } else {
        glDisableClientState(array);
    }
}

void restoreClientArrayState(const ClientArrayState& state) {
    glClientActiveTexture(GL_TEXTURE0);
    glBindBuffer(GL_ARRAY_BUFFER, static_cast<GLuint>(state.arrayBufferBinding));

    glVertexPointer(
        state.vertexSize,
        static_cast<GLenum>(state.vertexType),
        state.vertexStride,
        state.vertexPointer);
    glColorPointer(
        state.colorSize,
        static_cast<GLenum>(state.colorType),
        state.colorStride,
        state.colorPointer);
    glTexCoordPointer(
        state.textureCoordinateSize,
        static_cast<GLenum>(state.textureCoordinateType),
        state.textureCoordinateStride,
        state.textureCoordinatePointer);

    setClientState(GL_VERTEX_ARRAY, state.vertexArrayEnabled);
    setClientState(GL_COLOR_ARRAY, state.colorArrayEnabled);
    setClientState(GL_TEXTURE_COORD_ARRAY, state.textureCoordinateArrayEnabled);

    glClientActiveTexture(static_cast<GLenum>(state.clientActiveTexture));
}

void drawImmediateBatch(GLenum mode, const ImmediateVertex* vertices, std::size_t count) {
    if (vertices == nullptr || count == 0) {
        return;
    }
    if (!isSupportedImmediateMode(mode)) {
        logUnsupportedImmediateModeOnce(mode);
        return;
    }

    const ClientArrayState previous = captureClientArrayState();

    glClientActiveTexture(GL_TEXTURE0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_COLOR_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);

    glVertexPointer(
        2,
        GL_FLOAT,
        static_cast<GLsizei>(sizeof(ImmediateVertex)),
        &vertices[0].x);
    glTexCoordPointer(
        2,
        GL_FLOAT,
        static_cast<GLsizei>(sizeof(ImmediateVertex)),
        &vertices[0].s);
    glColorPointer(
        4,
        GL_UNSIGNED_BYTE,
        static_cast<GLsizei>(sizeof(ImmediateVertex)),
        &vertices[0].red);
    glDrawArrays(mode, 0, static_cast<GLsizei>(count));

    restoreClientArrayState(previous);
}

void seriousIOSBegin(GLenum mode) {
    ImmediateState& state = gImmediateState;
    if (state.active && !gLoggedNestedBegin) {
        gLoggedNestedBegin = true;
        SeriousIOS_DiagnosticsLog(
            "gl-compat",
            "immediate_mode_nested_begin previous=0x%04X next=0x%04X",
            static_cast<unsigned int>(state.mode),
            static_cast<unsigned int>(mode));
    }
    state.active = true;
    state.overflowed = false;
    state.mode = mode;
    state.vertexCount = 0;
}

void seriousIOSEnd(void) {
    ImmediateState& state = gImmediateState;
    if (!state.active) {
        if (!gLoggedEndWithoutBegin) {
            gLoggedEndWithoutBegin = true;
            SeriousIOS_DiagnosticsLog("gl-compat", "immediate_mode_end_without_begin");
        }
        return;
    }

    state.active = false;
    if (state.overflowed) {
        SeriousIOS_DiagnosticsLog(
            "gl-compat",
            "immediate_mode_vertex_overflow primitive=0x%04X limit=%lu",
            static_cast<unsigned int>(state.mode),
            static_cast<unsigned long>(state.vertices.size()));
    }
    drawImmediateBatch(state.mode, state.vertices.data(), state.vertexCount);
    state.vertexCount = 0;
}

void seriousIOSColor4ubv(const GLubyte* color) {
    if (color == nullptr) {
        return;
    }
    ImmediateState& state = gImmediateState;
    std::memcpy(state.currentColor, color, sizeof(state.currentColor));
    glColor4ub(color[0], color[1], color[2], color[3]);
}

void seriousIOSTexCoord2f(GLfloat s, GLfloat t) {
    ImmediateState& state = gImmediateState;
    state.currentS = s;
    state.currentT = t;
    glMultiTexCoord4f(GL_TEXTURE0, s, t, 0.0f, 1.0f);
}

void seriousIOSVertex2f(GLfloat x, GLfloat y) {
    ImmediateState& state = gImmediateState;
    if (!state.active) {
        if (!gLoggedVertexOutsideBegin) {
            gLoggedVertexOutsideBegin = true;
            SeriousIOS_DiagnosticsLog("gl-compat", "immediate_mode_vertex_outside_begin");
        }
        return;
    }
    if (state.vertexCount >= state.vertices.size()) {
        state.overflowed = true;
        return;
    }

    ImmediateVertex& vertex = state.vertices[state.vertexCount++];
    vertex.x = x;
    vertex.y = y;
    vertex.s = state.currentS;
    vertex.t = state.currentT;
    vertex.red = state.currentColor[0];
    vertex.green = state.currentColor[1];
    vertex.blue = state.currentColor[2];
    vertex.alpha = state.currentColor[3];
}

template <typename Function>
void* immediateFunctionAddress(Function function) {
    static_assert(std::is_pointer<Function>::value, "function pointer required");
    static_assert(sizeof(Function) == sizeof(void*), "unexpected function pointer size");
    void* address = nullptr;
    std::memcpy(&address, &function, sizeof(address));
    return address;
}

void setImmediateCompatibilityError(const char* format, const char* detail) {
    std::snprintf(
        gImmediateCompatibilityError,
        sizeof(gImmediateCompatibilityError),
        format,
        detail == nullptr ? "unknown" : detail);
    gImmediateCompatibilityError[sizeof(gImmediateCompatibilityError) - 1] = '\0';
}

void setImmediateCompatibilityErrorCode(const char* operation, GLenum error) {
    std::snprintf(
        gImmediateCompatibilityError,
        sizeof(gImmediateCompatibilityError),
        "OpenGL ES 1.1 immediate-mode compatibility %s failed with error 0x%04X",
        operation == nullptr ? "operation" : operation,
        static_cast<unsigned int>(error));
    gImmediateCompatibilityError[sizeof(gImmediateCompatibilityError) - 1] = '\0';
}

void* immediateFunction(const char* procedure) {
    if (procedure == nullptr || *procedure == '\0') {
        return nullptr;
    }
#define MAP_IMMEDIATE_FUNCTION(name, function) \
    if (std::strcmp(procedure, name) == 0) { \
        return immediateFunctionAddress(&function); \
    }
    MAP_IMMEDIATE_FUNCTION("glBegin", seriousIOSBegin)
    MAP_IMMEDIATE_FUNCTION("glEnd", seriousIOSEnd)
    MAP_IMMEDIATE_FUNCTION("glColor4ubv", seriousIOSColor4ubv)
    MAP_IMMEDIATE_FUNCTION("glTexCoord2f", seriousIOSTexCoord2f)
    MAP_IMMEDIATE_FUNCTION("glVertex2f", seriousIOSVertex2f)
#undef MAP_IMMEDIATE_FUNCTION
    return nullptr;
}

bool runImmediateModeSmokeTest() {
    if (gImmediateModeSmokeTestPassed) {
        return true;
    }

    for (int index = 0; index < 64 && glGetError() != GL_NO_ERROR; ++index) {
    }

    const GLubyte white[4] = {0xFF, 0xFF, 0xFF, 0xFF};
    seriousIOSBegin(GL_LINES);
    seriousIOSColor4ubv(white);
    seriousIOSTexCoord2f(0.0f, 0.0f);
    seriousIOSVertex2f(0.0f, 0.0f);
    seriousIOSVertex2f(0.0f, 0.0f);
    seriousIOSEnd();

    const GLenum error = glGetError();
    if (error != GL_NO_ERROR) {
        setImmediateCompatibilityErrorCode("smoke test", error);
        return false;
    }
    gImmediateModeSmokeTestPassed = true;
    return true;
}

} // namespace

extern "C" void* SeriousIOS_GetOpenGLImmediateCompatProcAddress(
    const char* procedure) {
    return immediateFunction(procedure);
}

extern "C" bool SeriousIOS_ValidateOpenGLImmediateCompatibility(void) {
    gImmediateCompatibilityError[0] = '\0';

    static constexpr std::array<const char*, 5> requiredProcedures = {
        "glBegin",
        "glEnd",
        "glColor4ubv",
        "glTexCoord2f",
        "glVertex2f",
    };
    for (const char* procedure : requiredProcedures) {
        if (immediateFunction(procedure) == nullptr) {
            setImmediateCompatibilityError(
                "OpenGL ES 1.1 immediate-mode procedure is missing: %s",
                procedure);
            return false;
        }
    }

    return runImmediateModeSmokeTest();
}

extern "C" const char* SeriousIOS_GetOpenGLImmediateCompatibilityError(void) {
    return gImmediateCompatibilityError;
}
