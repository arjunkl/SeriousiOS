#include <OpenGLES/ES1/gl.h>
#include <OpenGLES/ES1/glext.h>

#include <cstring>

#define SERIOUSIOS_GL_EXPORT \
    extern "C" __attribute__((used, visibility("default")))

namespace {

void convertMatrix(const double* source, GLfloat* destination) {
    if (source == nullptr || destination == nullptr) {
        return;
    }
    for (int index = 0; index < 16; ++index) {
        destination[index] = static_cast<GLfloat>(source[index]);
    }
}

} // namespace

SERIOUSIOS_GL_EXPORT void glClearDepth(double depth) {
    glClearDepthf(static_cast<GLclampf>(depth));
}

SERIOUSIOS_GL_EXPORT void glDepthRange(double nearValue, double farValue) {
    glDepthRangef(
        static_cast<GLclampf>(nearValue),
        static_cast<GLclampf>(farValue));
}

SERIOUSIOS_GL_EXPORT void glOrtho(
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

SERIOUSIOS_GL_EXPORT void glFrustum(
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

SERIOUSIOS_GL_EXPORT void glClipPlane(GLenum plane, const double* equation) {
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

SERIOUSIOS_GL_EXPORT void glGetClipPlane(GLenum plane, double* equation) {
    if (equation == nullptr) {
        return;
    }
    GLfloat converted[4] = {};
    glGetClipPlanef(plane, converted);
    for (int index = 0; index < 4; ++index) {
        equation[index] = static_cast<double>(converted[index]);
    }
}

SERIOUSIOS_GL_EXPORT void glGetDoublev(GLenum name, double* values) {
    if (values == nullptr) {
        return;
    }
    GLfloat converted[16] = {};
    glGetFloatv(name, converted);
    for (int index = 0; index < 16; ++index) {
        values[index] = static_cast<double>(converted[index]);
    }
}

SERIOUSIOS_GL_EXPORT void glLoadMatrixd(const double* matrix) {
    GLfloat converted[16] = {};
    convertMatrix(matrix, converted);
    glLoadMatrixf(converted);
}

SERIOUSIOS_GL_EXPORT void glMultMatrixd(const double* matrix) {
    GLfloat converted[16] = {};
    convertMatrix(matrix, converted);
    glMultMatrixf(converted);
}

SERIOUSIOS_GL_EXPORT void glRotated(double angle, double x, double y, double z) {
    glRotatef(
        static_cast<GLfloat>(angle),
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

SERIOUSIOS_GL_EXPORT void glScaled(double x, double y, double z) {
    glScalef(
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

SERIOUSIOS_GL_EXPORT void glTranslated(double x, double y, double z) {
    glTranslatef(
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

SERIOUSIOS_GL_EXPORT void glNormal3d(double x, double y, double z) {
    glNormal3f(
        static_cast<GLfloat>(x),
        static_cast<GLfloat>(y),
        static_cast<GLfloat>(z));
}

SERIOUSIOS_GL_EXPORT void glColor3d(double red, double green, double blue) {
    glColor4f(
        static_cast<GLfloat>(red),
        static_cast<GLfloat>(green),
        static_cast<GLfloat>(blue),
        1.0f);
}

SERIOUSIOS_GL_EXPORT void glColor4d(
    double red,
    double green,
    double blue,
    double alpha) {
    glColor4f(
        static_cast<GLfloat>(red),
        static_cast<GLfloat>(green),
        static_cast<GLfloat>(blue),
        static_cast<GLfloat>(alpha));
}

// iOS presents a single UIKit-owned color renderbuffer. Desktop read/draw
// buffer selection and polygon raster modes have no equivalent in OpenGL ES 1.
SERIOUSIOS_GL_EXPORT void glDrawBuffer(GLenum mode) {
    (void)mode;
}

SERIOUSIOS_GL_EXPORT void glReadBuffer(GLenum mode) {
    (void)mode;
}

SERIOUSIOS_GL_EXPORT void glPolygonMode(GLenum face, GLenum mode) {
    (void)face;
    (void)mode;
}

SERIOUSIOS_GL_EXPORT void glPushAttrib(GLbitfield mask) {
    (void)mask;
}

SERIOUSIOS_GL_EXPORT void glPopAttrib(void) {
}

SERIOUSIOS_GL_EXPORT void glPushClientAttrib(GLbitfield mask) {
    (void)mask;
}

SERIOUSIOS_GL_EXPORT void glPopClientAttrib(void) {
}

SERIOUSIOS_GL_EXPORT void glLineStipple(GLint factor, GLushort pattern) {
    (void)factor;
    (void)pattern;
}

SERIOUSIOS_GL_EXPORT void glPolygonStipple(const GLubyte* mask) {
    (void)mask;
}

SERIOUSIOS_GL_EXPORT void glGetPolygonStipple(GLubyte* mask) {
    if (mask != nullptr) {
        std::memset(mask, 0xFF, 128);
    }
}

SERIOUSIOS_GL_EXPORT void glEdgeFlag(GLboolean flag) {
    (void)flag;
}

SERIOUSIOS_GL_EXPORT void glEdgeFlagv(const GLboolean* flag) {
    (void)flag;
}

SERIOUSIOS_GL_EXPORT GLint glRenderMode(GLenum mode) {
    (void)mode;
    return 0;
}

SERIOUSIOS_GL_EXPORT void glClearAccum(
    GLfloat red,
    GLfloat green,
    GLfloat blue,
    GLfloat alpha) {
    (void)red;
    (void)green;
    (void)blue;
    (void)alpha;
}

SERIOUSIOS_GL_EXPORT void glAccum(GLenum operation, GLfloat value) {
    (void)operation;
    (void)value;
}

SERIOUSIOS_GL_EXPORT void glLockArraysEXT(GLint first, GLsizei count) {
    (void)first;
    (void)count;
}

SERIOUSIOS_GL_EXPORT void glUnlockArraysEXT(void) {
}

SERIOUSIOS_GL_EXPORT void glActiveTextureARB(GLenum texture) {
    glActiveTexture(texture);
}

SERIOUSIOS_GL_EXPORT void glClientActiveTextureARB(GLenum texture) {
    glClientActiveTexture(texture);
}

SERIOUSIOS_GL_EXPORT void glBindBufferARB(GLenum target, GLuint buffer) {
    glBindBuffer(target, buffer);
}

SERIOUSIOS_GL_EXPORT void glBufferDataARB(
    GLenum target,
    GLsizeiptr size,
    const GLvoid* data,
    GLenum usage) {
    glBufferData(target, size, data, usage);
}

SERIOUSIOS_GL_EXPORT void glBufferSubDataARB(
    GLenum target,
    GLintptr offset,
    GLsizeiptr size,
    const GLvoid* data) {
    glBufferSubData(target, offset, size, data);
}

SERIOUSIOS_GL_EXPORT void glDeleteBuffersARB(GLsizei count, const GLuint* buffers) {
    glDeleteBuffers(count, buffers);
}

SERIOUSIOS_GL_EXPORT void glGenBuffersARB(GLsizei count, GLuint* buffers) {
    glGenBuffers(count, buffers);
}

SERIOUSIOS_GL_EXPORT GLboolean glIsBufferARB(GLuint buffer) {
    return glIsBuffer(buffer);
}

SERIOUSIOS_GL_EXPORT void glCompressedTexImage2DARB(
    GLenum target,
    GLint level,
    GLenum internalFormat,
    GLsizei width,
    GLsizei height,
    GLint border,
    GLsizei imageSize,
    const GLvoid* data) {
    glCompressedTexImage2D(
        target,
        level,
        internalFormat,
        width,
        height,
        border,
        imageSize,
        data);
}

SERIOUSIOS_GL_EXPORT void glCompressedTexSubImage2DARB(
    GLenum target,
    GLint level,
    GLint xOffset,
    GLint yOffset,
    GLsizei width,
    GLsizei height,
    GLenum format,
    GLsizei imageSize,
    const GLvoid* data) {
    glCompressedTexSubImage2D(
        target,
        level,
        xOffset,
        yOffset,
        width,
        height,
        format,
        imageSize,
        data);
}

#undef SERIOUSIOS_GL_EXPORT
