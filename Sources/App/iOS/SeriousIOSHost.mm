#import <UIKit/UIKit.h>
#import <QuartzCore/CAEAGLLayer.h>
#import <OpenGLES/EAGL.h>
#import <OpenGLES/ES2/gl.h>

#include "SeriousIOSPlatformBridge.h"

#if defined(SERIOUSIOS_TFE)
extern "C" bool SeriousIOS_TFE_RegisterEntitySymbols() noexcept;
extern "C" bool SeriousIOS_TFE_RegisterRuntimeSymbols() noexcept;
static NSString* const kEncounterName = @"The First Encounter";
#elif defined(SERIOUSIOS_TSE)
extern "C" bool SeriousIOS_TSE_RegisterEntitySymbols() noexcept;
extern "C" bool SeriousIOS_TSE_RegisterRuntimeSymbols() noexcept;
static NSString* const kEncounterName = @"The Second Encounter";
#else
#error Define SERIOUSIOS_TFE or SERIOUSIOS_TSE
#endif

namespace {

bool registerRuntimeSymbols() noexcept {
#if defined(SERIOUSIOS_TFE)
    return SeriousIOS_TFE_RegisterEntitySymbols()
        && SeriousIOS_TFE_RegisterRuntimeSymbols();
#else
    return SeriousIOS_TSE_RegisterEntitySymbols()
        && SeriousIOS_TSE_RegisterRuntimeSymbols();
#endif
}

} // namespace

@interface SeriousIOSRenderView : UIView
@end

@implementation SeriousIOSRenderView {
    EAGLContext* _context;
    GLuint _framebuffer;
    GLuint _colorRenderbuffer;
    GLuint _depthRenderbuffer;
    GLint _drawableWidth;
    GLint _drawableHeight;
}

+ (Class)layerClass {
    return [CAEAGLLayer class];
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self == nil) {
        return nil;
    }

    self.contentScaleFactor = UIScreen.mainScreen.nativeScale;
    self.multipleTouchEnabled = YES;
    self.backgroundColor = UIColor.blackColor;

    CAEAGLLayer* layer = (CAEAGLLayer*)self.layer;
    layer.opaque = YES;
    layer.drawableProperties = @{
        kEAGLDrawablePropertyRetainedBacking: @NO,
        kEAGLDrawablePropertyColorFormat: kEAGLColorFormatRGBA8,
    };

    _context = [[EAGLContext alloc] initWithAPI:kEAGLRenderingAPIOpenGLES2];
    NSAssert(_context != nil, @"Unable to create an OpenGL ES 2 context");
    SeriousIOS_SetPresentCallback(&SeriousIOSPresent, (__bridge void*)self);
    return self;
}

- (void)dealloc {
    SeriousIOS_SetPresentCallback(nullptr, nullptr);
    [self destroyDrawable];
    if (EAGLContext.currentContext == _context) {
        [EAGLContext setCurrentContext:nil];
    }
}

- (void)layoutSubviews {
    [super layoutSubviews];
    [self createDrawable];
}

- (void)createDrawable {
    [self destroyDrawable];
    if (![EAGLContext setCurrentContext:_context]) {
        return;
    }

    glGenFramebuffers(1, &_framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, _framebuffer);

    glGenRenderbuffers(1, &_colorRenderbuffer);
    glBindRenderbuffer(GL_RENDERBUFFER, _colorRenderbuffer);
    [_context renderbufferStorage:GL_RENDERBUFFER fromDrawable:(CAEAGLLayer*)self.layer];
    glGetRenderbufferParameteriv(GL_RENDERBUFFER, GL_RENDERBUFFER_WIDTH, &_drawableWidth);
    glGetRenderbufferParameteriv(GL_RENDERBUFFER, GL_RENDERBUFFER_HEIGHT, &_drawableHeight);
    glFramebufferRenderbuffer(
        GL_FRAMEBUFFER,
        GL_COLOR_ATTACHMENT0,
        GL_RENDERBUFFER,
        _colorRenderbuffer);

    glGenRenderbuffers(1, &_depthRenderbuffer);
    glBindRenderbuffer(GL_RENDERBUFFER, _depthRenderbuffer);
    glRenderbufferStorage(
        GL_RENDERBUFFER,
        GL_DEPTH_COMPONENT16,
        _drawableWidth,
        _drawableHeight);
    glFramebufferRenderbuffer(
        GL_FRAMEBUFFER,
        GL_DEPTH_ATTACHMENT,
        GL_RENDERBUFFER,
        _depthRenderbuffer);

    NSAssert(
        glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE,
        @"SeriousiOS EAGL framebuffer is incomplete");

    glViewport(0, 0, _drawableWidth, _drawableHeight);
    glClearColor(0.035f, 0.035f, 0.045f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    SeriousIOS_SetSDLWindowSize(_drawableWidth, _drawableHeight);
    [self presentDrawable];
}

- (void)destroyDrawable {
    if (_context == nil || ![EAGLContext setCurrentContext:_context]) {
        return;
    }
    if (_depthRenderbuffer != 0) {
        glDeleteRenderbuffers(1, &_depthRenderbuffer);
        _depthRenderbuffer = 0;
    }
    if (_colorRenderbuffer != 0) {
        glDeleteRenderbuffers(1, &_colorRenderbuffer);
        _colorRenderbuffer = 0;
    }
    if (_framebuffer != 0) {
        glDeleteFramebuffers(1, &_framebuffer);
        _framebuffer = 0;
    }
    _drawableWidth = 0;
    _drawableHeight = 0;
    SeriousIOS_SetSDLWindowSize(0, 0);
}

- (void)presentDrawable {
    if (_colorRenderbuffer == 0 || ![EAGLContext setCurrentContext:_context]) {
        return;
    }
    glBindRenderbuffer(GL_RENDERBUFFER, _colorRenderbuffer);
    [_context presentRenderbuffer:GL_RENDERBUFFER];
}

static void SeriousIOSPresent(void* context) {
    SeriousIOSRenderView* view = (__bridge SeriousIOSRenderView*)context;
    [view presentDrawable];
}

@end

@interface SeriousIOSViewController : UIViewController
@end

@implementation SeriousIOSViewController

- (void)loadView {
    self.view = [[SeriousIOSRenderView alloc] initWithFrame:UIScreen.mainScreen.bounds];
}

- (BOOL)prefersStatusBarHidden {
    return YES;
}

- (UIInterfaceOrientationMask)supportedInterfaceOrientations {
    return UIInterfaceOrientationMaskLandscape;
}

- (BOOL)shouldAutorotate {
    return YES;
}

@end

@interface SeriousIOSAppDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic, strong) UIWindow* window;
@end

@implementation SeriousIOSAppDelegate

- (BOOL)application:(UIApplication*)application
    didFinishLaunchingWithOptions:(NSDictionary*)launchOptions {
    (void)application;
    (void)launchOptions;

    if (!registerRuntimeSymbols()) {
        NSLog(@"SeriousiOS static runtime registration failed for %@", kEncounterName);
        return NO;
    }

    NSLog(@"SeriousiOS UIKit host initialized for %@", kEncounterName);
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController = [[SeriousIOSViewController alloc] init];
    [self.window makeKeyAndVisible];
    return YES;
}

@end

int main(int argc, char* argv[]) {
    @autoreleasepool {
        return UIApplicationMain(
            argc,
            argv,
            nil,
            NSStringFromClass(SeriousIOSAppDelegate.class));
    }
}
