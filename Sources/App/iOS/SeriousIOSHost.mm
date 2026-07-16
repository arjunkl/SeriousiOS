#import <UIKit/UIKit.h>
#import <QuartzCore/CAEAGLLayer.h>
#import <OpenGLES/EAGL.h>
#import <OpenGLES/ES2/gl.h>

#include "SeriousIOSEngineStartup.h"
#include "SeriousIOSPlatformBridge.h"

#if defined(SERIOUSIOS_TFE)
extern "C" bool SeriousIOS_TFE_RegisterEntitySymbols() noexcept;
extern "C" bool SeriousIOS_TFE_RegisterRuntimeSymbols() noexcept;
static NSString* const kEncounterName = @"The First Encounter";
static NSString* const kEncounterPathComponent = @"TFE";
#elif defined(SERIOUSIOS_TSE)
extern "C" bool SeriousIOS_TSE_RegisterEntitySymbols() noexcept;
extern "C" bool SeriousIOS_TSE_RegisterRuntimeSymbols() noexcept;
static NSString* const kEncounterName = @"The Second Encounter";
static NSString* const kEncounterPathComponent = @"TSE";
#else
#error Define SERIOUSIOS_TFE or SERIOUSIOS_TSE
#endif

@class SeriousIOSRenderView;
static void SeriousIOSPresent(void* context);
static int SeriousIOSMakeCurrent(void* context);

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

NSURL* createEncounterDirectory(
    NSFileManager* fileManager,
    NSURL* root,
    NSString* category,
    NSError** error) {
    NSURL* directory = [[[root URLByAppendingPathComponent:@"SeriousIOS" isDirectory:YES]
        URLByAppendingPathComponent:kEncounterPathComponent isDirectory:YES]
        URLByAppendingPathComponent:category isDirectory:YES];
    if (![fileManager createDirectoryAtURL:directory
               withIntermediateDirectories:YES
                                attributes:nil
                                     error:error]) {
        return nil;
    }
    return directory;
}

bool configurePlatformPaths() {
    NSFileManager* fileManager = NSFileManager.defaultManager;
    NSError* error = nil;

    NSURL* documentsRoot = [fileManager URLsForDirectory:NSDocumentDirectory
                                                inDomains:NSUserDomainMask].firstObject;
    NSURL* supportRoot = [fileManager URLsForDirectory:NSApplicationSupportDirectory
                                              inDomains:NSUserDomainMask].firstObject;
    NSURL* cacheRoot = [fileManager URLsForDirectory:NSCachesDirectory
                                            inDomains:NSUserDomainMask].firstObject;
    NSURL* temporaryRoot = [NSURL fileURLWithPath:NSTemporaryDirectory() isDirectory:YES];

    NSURL* dataDirectory = createEncounterDirectory(
        fileManager, documentsRoot, @"GameData", &error);
    NSURL* userDirectory = createEncounterDirectory(
        fileManager, supportRoot, @"User", &error);
    NSURL* cacheDirectory = createEncounterDirectory(
        fileManager, cacheRoot, @"Cache", &error);
    NSURL* temporaryDirectory = createEncounterDirectory(
        fileManager, temporaryRoot, @"Temporary", &error);

    NSString* executablePath = NSBundle.mainBundle.executablePath;
    if (error != nil
        || executablePath.length == 0
        || dataDirectory == nil
        || userDirectory == nil
        || cacheDirectory == nil
        || temporaryDirectory == nil) {
        NSLog(@"SeriousiOS path configuration failed: %@", error);
        return false;
    }

    return SeriousIOS_ConfigurePaths(
        executablePath.fileSystemRepresentation,
        dataDirectory.path.fileSystemRepresentation,
        userDirectory.path.fileSystemRepresentation,
        cacheDirectory.path.fileSystemRepresentation,
        temporaryDirectory.path.fileSystemRepresentation);
}

} // namespace

@interface SeriousIOSRenderView : UIView
- (void)presentDrawable;
@end

@implementation SeriousIOSRenderView {
    EAGLContext* _context;
    GLuint _framebuffer;
    GLuint _colorRenderbuffer;
    GLuint _depthRenderbuffer;
    GLint _drawableWidth;
    GLint _drawableHeight;
    UILabel* _startupLabel;
    BOOL _startupScheduled;
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
    SeriousIOS_SetGLContext((__bridge void*)_context, &SeriousIOSMakeCurrent);

    _startupLabel = [[UILabel alloc] initWithFrame:CGRectZero];
    _startupLabel.translatesAutoresizingMaskIntoConstraints = NO;
    _startupLabel.textAlignment = NSTextAlignmentCenter;
    _startupLabel.numberOfLines = 0;
    _startupLabel.font = [UIFont monospacedSystemFontOfSize:15.0 weight:UIFontWeightMedium];
    _startupLabel.textColor = UIColor.whiteColor;
    _startupLabel.text = [NSString stringWithFormat:@"SeriousiOS %@\nPreparing core engine checkpoint…", kEncounterName];
    [self addSubview:_startupLabel];
    [NSLayoutConstraint activateConstraints:@[
        [_startupLabel.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_startupLabel.centerYAnchor constraintEqualToAnchor:self.centerYAnchor],
        [_startupLabel.leadingAnchor constraintGreaterThanOrEqualToAnchor:self.safeAreaLayoutGuide.leadingAnchor constant:24.0],
        [_startupLabel.trailingAnchor constraintLessThanOrEqualToAnchor:self.safeAreaLayoutGuide.trailingAnchor constant:-24.0],
    ]];
    return self;
}

- (void)dealloc {
    SeriousIOS_SetPresentCallback(nullptr, nullptr);
    SeriousIOS_SetGLContext(nullptr, nullptr);
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
    [self scheduleCoreEngineStartupIfNeeded];
}

- (void)scheduleCoreEngineStartupIfNeeded {
    if (_startupScheduled || _drawableWidth <= 0 || _drawableHeight <= 0) {
        return;
    }
    _startupScheduled = YES;
    _startupLabel.text = [NSString stringWithFormat:@"SeriousiOS %@\nStarting core engine without game data…", kEncounterName];

    dispatch_async(dispatch_get_main_queue(), ^{
        const bool started = SeriousIOS_StartCoreEngine();
        if (started) {
            self->_startupLabel.textColor = UIColor.systemGreenColor;
            self->_startupLabel.text = [NSString stringWithFormat:
                @"SeriousiOS %@\nCore engine initialized\nWaiting for original game data import",
                kEncounterName];
            NSLog(@"SeriousiOS core engine checkpoint passed for %@", kEncounterName);
            return;
        }

        const char* startupError = SeriousIOS_GetEngineStartupError();
        NSString* errorText = startupError == nullptr
            ? @"Unknown startup failure"
            : [NSString stringWithUTF8String:startupError];
        self->_startupLabel.textColor = UIColor.systemRedColor;
        self->_startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nCore engine startup failed\n%@",
            kEncounterName,
            errorText];
        NSLog(@"SeriousiOS core engine checkpoint failed for %@: %@", kEncounterName, errorText);
    });
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

@end

static void SeriousIOSPresent(void* context) {
    SeriousIOSRenderView* view = (__bridge SeriousIOSRenderView*)context;
    [view presentDrawable];
}

static int SeriousIOSMakeCurrent(void* context) {
    EAGLContext* eaglContext = (__bridge EAGLContext*)context;
    return [EAGLContext setCurrentContext:eaglContext] ? 0 : -1;
}

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

    if (!configurePlatformPaths()) {
        return NO;
    }
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

- (void)applicationWillTerminate:(UIApplication*)application {
    (void)application;
    SeriousIOS_StopCoreEngine();
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
