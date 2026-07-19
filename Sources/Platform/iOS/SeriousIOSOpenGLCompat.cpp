#include "SeriousIOSPlatformBridge.h"

#include <OpenGLES/ES1/gl.h>
#include <OpenGLES/ES1/glext.h>

#include <array>
#include <cstdio>
#include <cstring>
#include <type_traits>

namespace {

char gCompatibilityError[512] = {};

template <typename Function>
void* functionAddress(Function function) {
    static_assert(std::is_pointer<Function>::value, "function pointer required");
    static_assert(sizeof(Function) == sizeof(void*), "unexpected function pointer size");
    void* address = nullptr;
    std::memcpy(&address, &function, sizeof(address));
    return address;
}

void setCompatibilityError(const char* format, const char* detail) {
    std::snprintf(
        gCompatibilityError,
        sizeof(gCompatibilityError),
        format,
        detail == nullptr ? "unknown" : detail);
    gCompatibilityError[sizeof(gCompatibilityError) - 1] = '\0';
}

void convertMatrix(const double* source, GLfloat* destination) {
    if (source == nullptr || destination == nullptr) {
        return;
    }
    for (int index = 0; index < 16; ++index) {
        destination[index] = static_cast<GLfloat>(source[index]);
    }
}

void seriousIOSClearDepth(double depth) {
    glClearDepthf(static_cast<GLclampf>(depth));
}

void seriousIOSDepthRange(double nearValue, double farValue) {
    glDepthRangef(
        static_cast<GLclampf>(nearValue),
        static_cast<GLclampf>(farValue));
}

void seriousIOSOrtho(
    double left,
    double right,
    double bottom,
    double top,
    double nearValue,
    double farValue) {
    glOrthof(
        static_cast<GLfloat>(left),
        static_cast<GLfloat>(right),
        static_cast<GLfloat>(bottom),
        static_cast<GLfloat>(top),
        static_cast<GLfloat>(nearValue),
        static_cast<GLfloat>(farValue));
}

void seriousIOSFrustum(
    double left,
    double right,
    double bottom,
    double top,
    double nearValue,
    double farValue) {
    glFrustumf(
        static_cast<GLfloat>(left),
        static_cast<GLfloat>(right),
        static_cast<GLfloat>(bottom),
        static_cast<GLfloat>(top),
        static_cast<GLfloat>(nearValue),
        static_cast<GLfloat>(farValue));
}

void seriousIOSClipPlane(GLenum plane, const double* equation) {
    if (equation == nullptr) {
        return;
    }
    const GLfloat converted[4] = {
        static_cast<GLfloat>(equation[0]),
        static_cast<GLfloat>(equation[1]),
        static_cast<GLfloat>(equation[2]),
        static_cast<GLfloat>(equation[3]),
    };
    glClipPlanef(plane, converted);
}

void seriousIOSGetClipPlane(GLenum plane, double* equation) {
    if (equation == nullptr) {
        return;
    }
    GLfloat converted[4] = {};
    glGetClipPlanef(plane, converted);
    for (int index = 0; index < 4; ++index) {
        equation[index] = static_cast<double>(converted[index]);
    }
}

void seriousIOSGetDoublev(GLenum name, double* values) {
    if (values == nullptr) {
        return;
    }
    GLfloat converted[16] = {};
    glGetFloatv(name, converted);
    for (int index = 0; index < 16; ++index) {
        values[index] = static_cast<double>(converted[index]);
    }
}

void seriousIOSLoadMatrixd(const double* matrix) {
    GLfloat converted[16] = {};
    convertMatrix(matrix, converted);
    glLoadMatrixf(converted);
}

void seriousIOSMultMatrixd(const double* matrix) {
    GLfloat converted[16] = {};
    convertMatrix(matrix, converted);
    glMultMatrixf(converted);
}

void seriousIOSRotated(double angle, double x, double y, double z) {
    glRotatef(
        static_cast<GLfloat>(angle),
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

void seriousIOSScaled(double x, double y, double z) {
    glScalef(
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

void seriousIOSTranslated(double x, double y, double z) {
    glTranslatef(
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

void seriousIOSNormal3d(double x, double y, double z) {
    glNormal3f(
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

void seriousIOSColor3d(double red, double green, double blue) {
    glColor4f(
        static_cast<GLfloat>(red),
        static_cast<GLfloat>(green),
        static_cast<GLfloat>(blue),
        1.0f);
}

void seriousIOSColor4d(double red, double green, double blue, double alpha) {
    glColor4f(
        static_cast<GLfloat>(red),
        static_cast<GLfloat>(green),
        static_cast<GLfloat>(blue),
        static_cast<GLfloat>(alpha));
}

void seriousIOSSingleBufferNoOp(GLenum value) {
    (void)value;
}

void seriousIOSPolygonModeNoOp(GLenum face, GLenum mode) {
    (void)face;
    (void)mode;
}

void seriousIOSAttributeNoOp(void) {
}

void seriousIOSAttributeMaskNoOp(GLbitfield mask) {
    (void)mask;
}

void seriousIOSLineStippleNoOp(GLint factor, GLushort pattern) {
    (void)factor;
    (void)pattern;
}

void seriousIOSPolygonStippleNoOp(const GLubyte* mask) {
    (void)mask;
}

void seriousIOSGetPolygonStippleNoOp(GLubyte* mask) {
    if (mask != nullptr) {
        std::memset(mask, 0xFF, 128);
    }
}

void seriousIOSEdgeFlagNoOp(GLboolean flag) {
    (void)flag;
}

void seriousIOSEdgeFlagvNoOp(const GLboolean* flag) {
    (void)flag;
}

GLint seriousIOSRenderModeNoOp(GLenum mode) {
    (void)mode;
    return 0;
}

void seriousIOSClearAccumNoOp(GLfloat red, GLfloat green, GLfloat blue, GLfloat alpha) {
    (void)red;
    (void)green;
    (void)blue;
    (void)alpha;
}

void seriousIOSAccumNoOp(GLenum operation, GLfloat value) {
    (void)operation;
    (void)value;
}

void seriousIOSLockArraysNoOp(GLint first, GLsizei count) {
    (void)first;
    (void)count;
}

void* directOpenGLES1Function(const char* procedure) {
    if (procedure == nullptr || *procedure == '\0') {
        return nullptr;
    }

#define MAP_GL_FUNCTION(name) \
    if (std::strcmp(procedure, #name) == 0) { \
        return functionAddress(&name); \
    }

    MAP_GL_FUNCTION(glActiveTexture)
    MAP_GL_FUNCTION(glAlphaFunc)
    MAP_GL_FUNCTION(glBindBuffer)
    MAP_GL_FUNCTION(glBindTexture)
    MAP_GL_FUNCTION(glBlendFunc)
    MAP_GL_FUNCTION(glBufferData)
    MAP_GL_FUNCTION(glBufferSubData)
    MAP_GL_FUNCTION(glClear)
    MAP_GL_FUNCTION(glClearColor)
    MAP_GL_FUNCTION(glClearStencil)
    MAP_GL_FUNCTION(glClientActiveTexture)
    MAP_GL_FUNCTION(glColor4f)
    MAP_GL_FUNCTION(glColor4ub)
    MAP_GL_FUNCTION(glColorMask)
    MAP_GL_FUNCTION(glColorPointer)
    MAP_GL_FUNCTION(glCompressedTexImage2D)
    MAP_GL_FUNCTION(glCompressedTexSubImage2D)
    MAP_GL_FUNCTION(glCopyTexImage2D)
    MAP_GL_FUNCTION(glCopyTexSubImage2D)
    MAP_GL_FUNCTION(glCullFace)
    MAP_GL_FUNCTION(glDeleteBuffers)
    MAP_GL_FUNCTION(glDeleteTextures)
    MAP_GL_FUNCTION(glDepthFunc)
    MAP_GL_FUNCTION(glDepthMask)
    MAP_GL_FUNCTION(glDisable)
    MAP_GL_FUNCTION(glDisableClientState)
    MAP_GL_FUNCTION(glDrawArrays)
    MAP_GL_FUNCTION(glDrawElements)
    MAP_GL_FUNCTION(glEnable)
    MAP_GL_FUNCTION(glEnableClientState)
    MAP_GL_FUNCTION(glFinish)
    MAP_GL_FUNCTION(glFlush)
    MAP_GL_FUNCTION(glFogf)
    MAP_GL_FUNCTION(glFogfv)
    MAP_GL_FUNCTION(glFrontFace)
    MAP_GL_FUNCTION(glGenBuffers)
    MAP_GL_FUNCTION(glGenTextures)
    MAP_GL_FUNCTION(glGetBooleanv)
    MAP_GL_FUNCTION(glGetBufferParameteriv)
    MAP_GL_FUNCTION(glGetError)
    MAP_GL_FUNCTION(glGetFloatv)
    MAP_GL_FUNCTION(glGetIntegerv)
    MAP_GL_FUNCTION(glGetPointerv)
    MAP_GL_FUNCTION(glGetString)
    MAP_GL_FUNCTION(glGetTexEnvfv)
    MAP_GL_FUNCTION(glGetTexEnviv)
    MAP_GL_FUNCTION(glGetTexParameterfv)
    MAP_GL_FUNCTION(glGetTexParameteriv)
    MAP_GL_FUNCTION(glHint)
    MAP_GL_FUNCTION(glIsBuffer)
    MAP_GL_FUNCTION(glIsEnabled)
    MAP_GL_FUNCTION(glIsTexture)
    MAP_GL_FUNCTION(glLightModelf)
    MAP_GL_FUNCTION(glLightModelfv)
    MAP_GL_FUNCTION(glLightf)
    MAP_GL_FUNCTION(glLightfv)
    MAP_GL_FUNCTION(glLineWidth)
    MAP_GL_FUNCTION(glLoadIdentity)
    MAP_GL_FUNCTION(glLoadMatrixf)
    MAP_GL_FUNCTION(glLogicOp)
    MAP_GL_FUNCTION(glMaterialf)
    MAP_GL_FUNCTION(glMaterialfv)
    MAP_GL_FUNCTION(glMatrixMode)
    MAP_GL_FUNCTION(glMultMatrixf)
    MAP_GL_FUNCTION(glMultiTexCoord4f)
    MAP_GL_FUNCTION(glNormal3f)
    MAP_GL_FUNCTION(glNormalPointer)
    MAP_GL_FUNCTION(glOrthof)
    MAP_GL_FUNCTION(glPixelStorei)
    MAP_GL_FUNCTION(glPointSize)
    MAP_GL_FUNCTION(glPolygonOffset)
    MAP_GL_FUNCTION(glPopMatrix)
    MAP_GL_FUNCTION(glPushMatrix)
    MAP_GL_FUNCTION(glReadPixels)
    MAP_GL_FUNCTION(glRotatef)
    MAP_GL_FUNCTION(glSampleCoverage)
    MAP_GL_FUNCTION(glScalef)
    MAP_GL_FUNCTION(glScissor)
    MAP_GL_FUNCTION(glShadeModel)
    MAP_GL_FUNCTION(glStencilFunc)
    MAP_GL_FUNCTION(glStencilMask)
    MAP_GL_FUNCTION(glStencilOp)
    MAP_GL_FUNCTION(glTexCoordPointer)
    MAP_GL_FUNCTION(glTexEnvf)
    MAP_GL_FUNCTION(glTexEnvfv)
    MAP_GL_FUNCTION(glTexEnvi)
    MAP_GL_FUNCTION(glTexEnviv)
    MAP_GL_FUNCTION(glTexImage2D)
    MAP_GL_FUNCTION(glTexParameterf)
    MAP_GL_FUNCTION(glTexParameterfv)
    MAP_GL_FUNCTION(glTexParameteri)
    MAP_GL_FUNCTION(glTexParameteriv)
    MAP_GL_FUNCTION(glTexSubImage2D)
    MAP_GL_FUNCTION(glTranslatef)
    MAP_GL_FUNCTION(glVertexPointer)
    MAP_GL_FUNCTION(glViewport)

#undef MAP_GL_FUNCTION

#define MAP_COMPAT_FUNCTION(name, function) \
    if (std::strcmp(procedure, name) == 0) { \
        return functionAddress(&function); \
    }

    MAP_COMPAT_FUNCTION("glClearDepth", seriousIOSClearDepth)
    MAP_COMPAT_FUNCTION("glDepthRange", seriousIOSDepthRange)
    MAP_COMPAT_FUNCTION("glOrtho", seriousIOSOrtho)
    MAP_COMPAT_FUNCTION("glFrustum", seriousIOSFrustum)
    MAP_COMPAT_FUNCTION("glClipPlane", seriousIOSClipPlane)
    MAP_COMPAT_FUNCTION("glGetClipPlane", seriousIOSGetClipPlane)
    MAP_COMPAT_FUNCTION("glGetDoublev", seriousIOSGetDoublev)
    MAP_COMPAT_FUNCTION("glLoadMatrixd", seriousIOSLoadMatrixd)
    MAP_COMPAT_FUNCTION("glMultMatrixd", seriousIOSMultMatrixd)
    MAP_COMPAT_FUNCTION("glRotated", seriousIOSRotated)
    MAP_COMPAT_FUNCTION("glScaled", seriousIOSScaled)
    MAP_COMPAT_FUNCTION("glTranslated", seriousIOSTranslated)
    MAP_COMPAT_FUNCTION("glNormal3d", seriousIOSNormal3d)
    MAP_COMPAT_FUNCTION("glColor3d", seriousIOSColor3d)
    MAP_COMPAT_FUNCTION("glColor4d", seriousIOSColor4d)
    MAP_COMPAT_FUNCTION("glDrawBuffer", seriousIOSSingleBufferNoOp)
    MAP_COMPAT_FUNCTION("glReadBuffer", seriousIOSSingleBufferNoOp)
    MAP_COMPAT_FUNCTION("glPolygonMode", seriousIOSPolygonModeNoOp)
    MAP_COMPAT_FUNCTION("glPushAttrib", seriousIOSAttributeMaskNoOp)
    MAP_COMPAT_FUNCTION("glPopAttrib", seriousIOSAttributeNoOp)
    MAP_COMPAT_FUNCTION("glPushClientAttrib", seriousIOSAttributeMaskNoOp)
    MAP_COMPAT_FUNCTION("glPopClientAttrib", seriousIOSAttributeNoOp)
    MAP_COMPAT_FUNCTION("glLineStipple", seriousIOSLineStippleNoOp)
    MAP_COMPAT_FUNCTION("glPolygonStipple", seriousIOSPolygonStippleNoOp)
    MAP_COMPAT_FUNCTION("glGetPolygonStipple", seriousIOSGetPolygonStippleNoOp)
    MAP_COMPAT_FUNCTION("glEdgeFlag", seriousIOSEdgeFlagNoOp)
    MAP_COMPAT_FUNCTION("glEdgeFlagv", seriousIOSEdgeFlagvNoOp)
    MAP_COMPAT_FUNCTION("glRenderMode", seriousIOSRenderModeNoOp)
    MAP_COMPAT_FUNCTION("glClearAccum", seriousIOSClearAccumNoOp)
    MAP_COMPAT_FUNCTION("glAccum", seriousIOSAccumNoOp)
    MAP_COMPAT_FUNCTION("glLockArraysEXT", seriousIOSLockArraysNoOp)
    MAP_COMPAT_FUNCTION("glUnlockArraysEXT", seriousIOSAttributeNoOp)

    MAP_COMPAT_FUNCTION("glActiveTextureARB", glActiveTexture)
    MAP_COMPAT_FUNCTION("glClientActiveTextureARB", glClientActiveTexture)
    MAP_COMPAT_FUNCTION("glBindBufferARB", glBindBuffer)
    MAP_COMPAT_FUNCTION("glBufferDataARB", glBufferData)
    MAP_COMPAT_FUNCTION("glBufferSubDataARB", glBufferSubData)
    MAP_COMPAT_FUNCTION("glDeleteBuffersARB", glDeleteBuffers)
    MAP_COMPAT_FUNCTION("glGenBuffersARB", glGenBuffers)
    MAP_COMPAT_FUNCTION("glIsBufferARB", glIsBuffer)
    MAP_COMPAT_FUNCTION("glCompressedTexImage2DARB", glCompressedTexImage2D)
    MAP_COMPAT_FUNCTION("glCompressedTexSubImage2DARB", glCompressedTexSubImage2D)

#undef MAP_COMPAT_FUNCTION

    return nullptr;
}

} // namespace

extern "C" void* SeriousIOS_GetOpenGLCompatProcAddress(const char* procedure) {
    return directOpenGLES1Function(procedure);
}

extern "C" bool SeriousIOS_ValidateOpenGLCompatibility(void) {
    gCompatibilityError[0] = '\0';

    const GLubyte* version = glGetString(GL_VERSION);
    if (version == nullptr) {
        setCompatibilityError(
            "OpenGL ES 1.1 context validation failed: %s",
            "glGetString(GL_VERSION) returned null");
        return false;
    }

    static constexpr std::array<const char*, 31> requiredProcedures = {
        "glGetError",
        "glEnable",
        "glDisable",
        "glFrontFace",
        "glDepthMask",
        "glDepthFunc",
        "glBlendFunc",
        "glDepthRange",
        "glPolygonMode",
        "glShadeModel",
        "glDrawBuffer",
        "glAlphaFunc",
        "glColor4f",
        "glMatrixMode",
        "glLoadIdentity",
        "glEnableClientState",
        "glDisableClientState",
        "glPixelStorei",
        "glGetString",
        "glGetIntegerv",
        "glViewport",
        "glScissor",
        "glClearColor",
        "glClear",
        "glVertexPointer",
        "glTexCoordPointer",
        "glColorPointer",
        "glDrawElements",
        "glBindTexture",
        "glTexImage2D",
        "glTexSubImage2D",
    };

    for (const char* procedure : requiredProcedures) {
        if (directOpenGLES1Function(procedure) == nullptr) {
            setCompatibilityError(
                "OpenGL ES 1.1 compatibility procedure is missing: %s",
                procedure);
            return false;
        }
    }

    return true;
}

extern "C" const char* SeriousIOS_GetOpenGLCompatibilityError(void) {
    return gCompatibilityError;
}
