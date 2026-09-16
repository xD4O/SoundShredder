// A real AppKit process owns Finder activation, reopening, menus and shutdown.
#import <Cocoa/Cocoa.h>

@interface SoundShredderDelegate : NSObject <NSApplicationDelegate>
@property NSTask *manager;
@property NSPipe *ownerPipe;
@property NSStatusItem *statusItem;
@property NSString *resources;
@property NSString *profile;
@property NSArray<NSString *> *launchArguments;
@property BOOL mayTerminate;
@property BOOL quitPending;
@end

@implementation SoundShredderDelegate
- (void)record:(NSString *)event {
    NSString *path = [self.profile stringByAppendingPathComponent:@"native-launcher.log"];
    if (![[NSFileManager defaultManager] fileExistsAtPath:path])
        [[NSFileManager defaultManager] createFileAtPath:path contents:nil attributes:@{NSFilePosixPermissions: @0600}];
    NSFileHandle *log = [NSFileHandle fileHandleForWritingAtPath:path];
    [log seekToEndOfFile];
    [log writeData:[[NSString stringWithFormat:@"%@ %@\n", [NSDate date], event] dataUsingEncoding:NSUTF8StringEncoding]];
    [log closeFile];
}
- (void)showError:(NSString *)message {
    NSAlert *alert = [NSAlert new];
    alert.messageText = @"SoundShredder";
    alert.informativeText = message;
    [NSApp activateIgnoringOtherApps:YES];
    [alert runModal];
}
- (NSTask *)taskWithArguments:(NSArray<NSString *> *)arguments {
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:[self.resources stringByAppendingPathComponent:@"python/bin/python3.11"]];
    NSMutableArray *args = [NSMutableArray arrayWithArray:@[@"-I", [self.resources stringByAppendingPathComponent:@"desktop/bootstrap.py"]]];
    [args addObjectsFromArray:self.launchArguments];
    [args addObjectsFromArray:arguments];
    task.arguments = args;
    task.currentDirectoryURL = [NSURL fileURLWithPath:self.resources];
    NSMutableDictionary *env = [[[NSProcessInfo processInfo] environment] mutableCopy];
    [env removeObjectForKey:@"PYTHONHOME"];
    [env removeObjectForKey:@"PYTHONPATH"];
    env[@"SOUNDSHREDDER_DESKTOP_HOME"] = self.profile;
    task.environment = env;
    NSString *path = [self.profile stringByAppendingPathComponent:@"launcher.log"];
    if (![[NSFileManager defaultManager] fileExistsAtPath:path])
        [[NSFileManager defaultManager] createFileAtPath:path contents:nil attributes:@{NSFilePosixPermissions: @0600}];
    NSFileHandle *log = [NSFileHandle fileHandleForWritingAtPath:path];
    [log seekToEndOfFile];
    task.standardOutput = log;
    task.standardError = log;
    return task;
}
- (void)openWithSetup:(BOOL)setup {
    [self record:setup ? @"open-setup" : @"reopen-workspace"];
    NSTask *task = [self taskWithArguments:setup ? @[@"--reopen-only", @"--setup"] : @[@"--reopen-only"]];
    task.terminationHandler = ^(NSTask *finished) {
        if (finished.terminationStatus != 0) dispatch_async(dispatch_get_main_queue(), ^{
            [self showError:@"The workspace could not reopen. Check launcher.log in the SoundShredder support folder, then quit and reopen SoundShredder."];
        });
    };
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) [self showError:error.localizedDescription];
}
- (void)openWorkspace:(id)sender { [self openWithSetup:NO]; }
- (void)openSetup:(id)sender { [self openWithSetup:YES]; }
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    self.resources = [[NSBundle mainBundle] resourcePath];
    NSMutableArray *args = [NSMutableArray array];
    NSArray *incoming = [[NSProcessInfo processInfo] arguments];
    for (NSUInteger i = 1; i < incoming.count; i++) {
        if ([incoming[i] isEqualToString:@"--no-browser"]) [args addObject:incoming[i]];
        else if ([incoming[i] isEqualToString:@"--home"] && i + 1 < incoming.count) {
            [args addObject:incoming[i]];
            [args addObject:incoming[++i]];
        }
    }
    self.launchArguments = args;
    self.profile = [[[NSProcessInfo processInfo] environment] objectForKey:@"SOUNDSHREDDER_DESKTOP_HOME"];
    if (!self.profile) self.profile = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/SoundShredder"];
    NSUInteger home = [args indexOfObject:@"--home"];
    if (home != NSNotFound) self.profile = args[home + 1];
    NSError *error = nil;
    if (![[NSFileManager defaultManager] createDirectoryAtPath:self.profile withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions: @0700} error:&error]) {
        [self showError:error.localizedDescription]; self.mayTerminate = YES; [NSApp terminate:nil]; return;
    }
    NSData *platformData = [NSData dataWithContentsOfFile:[self.resources stringByAppendingPathComponent:@"desktop/platform.json"]];
    NSDictionary *platform = platformData ? [NSJSONSerialization JSONObjectWithData:platformData options:0 error:&error] : nil;
#if defined(__arm64__)
    NSString *machine = @"arm64";
#else
    NSString *machine = @"x86_64";
#endif
    if (![platform[@"machine"] isEqualToString:machine]) {
        [self showError:@"Download the matching Apple Silicon or Intel build. Open the Apple Silicon build natively rather than with Rosetta."];
        self.mayTerminate = YES; [NSApp terminate:nil]; return;
    }
    self.statusItem = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];
    self.statusItem.button.image = [NSImage imageWithSystemSymbolName:@"waveform" accessibilityDescription:@"SoundShredder"];
    self.statusItem.button.toolTip = @"SoundShredder";
    NSMenu *menu = [NSMenu new];
    NSMenuItem *workspace = [menu addItemWithTitle:@"Open SoundShredder" action:@selector(openWorkspace:) keyEquivalent:@""];
    workspace.target = self;
    NSMenuItem *setup = [menu addItemWithTitle:@"Setup and diagnostics" action:@selector(openSetup:) keyEquivalent:@""];
    setup.target = self;
    [menu addItem:[NSMenuItem separatorItem]];
    NSMenuItem *quit = [menu addItemWithTitle:@"Quit SoundShredder" action:@selector(terminate:) keyEquivalent:@"q"];
    quit.target = NSApp;
    self.statusItem.menu = menu;
    self.manager = [self taskWithArguments:@[@"--hosted"]];
    self.ownerPipe = [NSPipe pipe];
    self.manager.standardInput = self.ownerPipe;
    self.manager.terminationHandler = ^(NSTask *finished) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [self record:[NSString stringWithFormat:@"manager-exit:%d", finished.terminationStatus]];
            self.mayTerminate = YES;
            if (!self.quitPending) [NSApp terminate:nil];
        });
    };
    if (![self.manager launchAndReturnError:&error]) {
        [self showError:[NSString stringWithFormat:@"The bundled app could not start: %@. Re-extract the complete download into Applications.", error.localizedDescription]];
        self.mayTerminate = YES; [NSApp terminate:nil]; return;
    }
    [self record:@"native-app-started"];
}
- (BOOL)applicationShouldHandleReopen:(NSApplication *)application hasVisibleWindows:(BOOL)visible {
    if (self.manager && !self.quitPending) [self openWithSetup:NO];
    return NO;
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (self.mayTerminate) return NSTerminateNow;
    if (self.quitPending) return NSTerminateCancel;
    self.quitPending = YES;
    NSTask *quit = [self taskWithArguments:@[@"--quit"]];
    quit.terminationHandler = ^(NSTask *finished) {
        dispatch_async(dispatch_get_main_queue(), ^{
            self.quitPending = NO;
            if (finished.terminationStatus == 0) {
                self.mayTerminate = YES;
                [NSApp replyToApplicationShouldTerminate:YES];
            } else {
                [NSApp replyToApplicationShouldTerminate:NO];
                [self showError:@"SoundShredder is still setting up or processing audio. Finish or cancel processing in the workspace, then quit again. Setup and diagnostics has more details."];
            }
        });
    };
    NSError *error = nil;
    if (![quit launchAndReturnError:&error]) {
        self.quitPending = NO; [self showError:error.localizedDescription]; return NSTerminateCancel;
    }
    return NSTerminateLater;
}
- (void)applicationWillTerminate:(NSNotification *)notification {
    [self.ownerPipe.fileHandleForWriting closeFile];
    [self record:@"native-app-closed"];
}
@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyAccessory];
        static SoundShredderDelegate *delegate;
        delegate = [SoundShredderDelegate new];
        app.delegate = delegate;
        [app run];
    }
    return 0;
}
