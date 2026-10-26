#!/usr/bin/env python3
"""Generate a deterministic Xcode project using only Python's standard library."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "DualCam.xcodeproj"
objects = {}


def uid(name):
    return hashlib.sha256(name.encode()).hexdigest()[:24].upper()


def q(value):
    return json.dumps(str(value), ensure_ascii=False)


def array(values):
    return "(" + ", ".join(values) + ",)" if values else "()"


def obj(identity, isa, **fields):
    key = uid(identity)
    objects[key] = {"isa": isa, **fields}
    return key


def settings(values):
    return "{ " + " ".join(f"{key} = {q(value)};" for key, value in values.items()) + " }"


app_files = sorted((ROOT / "DualCam").glob("*.swift"))
test_files = sorted((ROOT / "DualCamTests").glob("*.swift"))
core_names = {"Recording.swift", "RecordingTimeline.swift", "DualMovieWriter.swift", "AudioBacklog.swift", "CaptureHealth.swift"}
references = {}
for path in [*app_files, *test_files, ROOT / "DualCam/Info.plist", ROOT / "DualCam/Assets.xcassets"]:
    relative = path.relative_to(ROOT).as_posix()
    file_type = {".swift": "sourcecode.swift", ".plist": "text.plist.xml", ".xcassets": "folder.assetcatalog"}[path.suffix]
    references[relative] = obj("file:" + relative, "PBXFileReference", lastKnownFileType=file_type,
                               path=q(path.name), sourceTree=q("<group>"))

app_product = obj("app-product", "PBXFileReference", explicitFileType="wrapper.application",
                  includeInIndex="0", path=q("DualCam.app"), sourceTree="BUILT_PRODUCTS_DIR")
test_product = obj("test-product", "PBXFileReference", explicitFileType="wrapper.cfbundle",
                   includeInIndex="0", path=q("DualCamTests.xctest"), sourceTree="BUILT_PRODUCTS_DIR")
app_group = obj("app-group", "PBXGroup", children=array([ref for path, ref in references.items() if path.startswith("DualCam/")]),
                path=q("DualCam"), sourceTree=q("<group>"))
test_group = obj("test-group", "PBXGroup", children=array([ref for path, ref in references.items() if path.startswith("DualCamTests/")]),
                 path=q("DualCamTests"), sourceTree=q("<group>"))
products = obj("products", "PBXGroup", children=array([app_product, test_product]), name="Products", sourceTree=q("<group>"))
main_group = obj("main-group", "PBXGroup", children=array([app_group, test_group, products]), sourceTree=q("<group>"))

common = {
    "SDKROOT": "iphoneos", "IPHONEOS_DEPLOYMENT_TARGET": "16.0", "SWIFT_VERSION": "5.0",
    "CLANG_ENABLE_MODULES": "YES", "CLANG_ENABLE_OBJC_ARC": "YES", "TARGETED_DEVICE_FAMILY": "1",
    "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator", "ENABLE_USER_SCRIPT_SANDBOXING": "YES",
}


def configurations(name, extra):
    configs = []
    for mode in ["Debug", "Release"]:
        values = {**common, "SWIFT_OPTIMIZATION_LEVEL": "-Onone" if mode == "Debug" else "-O",
                  "DEBUG_INFORMATION_FORMAT": "dwarf" if mode == "Debug" else "dwarf-with-dsym", **extra}
        if mode == "Debug":
            values.update({"SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG", "ENABLE_TESTABILITY": "YES"})
        configs.append(obj(name + ":" + mode, "XCBuildConfiguration", buildSettings=settings(values), name=mode))
    return obj(name + ":configs", "XCConfigurationList", buildConfigurations=array(configs),
               defaultConfigurationIsVisible="0", defaultConfigurationName="Release")


def phase(name, kind, paths):
    files = [obj(name + ":" + path, "PBXBuildFile", fileRef=references[path]) for path in paths]
    return obj(name, kind, buildActionMask="2147483647", files=array(files), runOnlyForDeploymentPostprocessing="0")


app_sources = phase("app-sources", "PBXSourcesBuildPhase", [p.relative_to(ROOT).as_posix() for p in app_files])
test_sources = phase("test-sources", "PBXSourcesBuildPhase", [
    *[p.relative_to(ROOT).as_posix() for p in app_files if p.name in core_names],
    *[p.relative_to(ROOT).as_posix() for p in test_files]
])
resources = phase("app-resources", "PBXResourcesBuildPhase", ["DualCam/Assets.xcassets"])
app_frameworks = phase("app-frameworks", "PBXFrameworksBuildPhase", [])
test_frameworks = phase("test-frameworks", "PBXFrameworksBuildPhase", [])

app = obj("app-target", "PBXNativeTarget", buildConfigurationList=configurations("app", {
    "PRODUCT_NAME": "$(TARGET_NAME)", "PRODUCT_BUNDLE_IDENTIFIER": "app.dualcam.personal",
    "INFOPLIST_FILE": "DualCam/Info.plist", "CODE_SIGN_STYLE": "Automatic",
    "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
    "LD_RUNPATH_SEARCH_PATHS": "$(inherited) @executable_path/Frameworks",
}), buildPhases=array([app_sources, app_frameworks, resources]), buildRules="()", dependencies="()",
          name="DualCam", productName="DualCam", productReference=app_product,
          productType=q("com.apple.product-type.application"))
tests = obj("test-target", "PBXNativeTarget", buildConfigurationList=configurations("tests", {
    "PRODUCT_NAME": "$(TARGET_NAME)", "PRODUCT_BUNDLE_IDENTIFIER": "app.dualcam.tests",
    "GENERATE_INFOPLIST_FILE": "YES", "CODE_SIGN_STYLE": "Automatic",
    "LD_RUNPATH_SEARCH_PATHS": "$(inherited) @executable_path/Frameworks @loader_path/Frameworks",
}), buildPhases=array([test_sources, test_frameworks]), buildRules="()", dependencies="()",
            name="DualCamTests", productName="DualCamTests", productReference=test_product,
            productType=q("com.apple.product-type.bundle.unit-test"))
project = obj("project", "PBXProject", attributes="{ LastUpgradeCheck = 1600; }",
              buildConfigurationList=configurations("project", {}), compatibilityVersion=q("Xcode 14.0"),
              developmentRegion="ko", hasScannedForEncodings="0", knownRegions="(ko, en, Base,)",
              mainGroup=main_group, productRefGroup=products, projectDirPath=q(""), projectRoot=q(""),
              targets=array([app, tests]))

PROJECT.mkdir(exist_ok=True)
lines = ["// !$*UTF8*$!", "{", "\tarchiveVersion = 1;", "\tclasses = {};", "\tobjectVersion = 56;", "\tobjects = {"]
for key, fields in objects.items():
    lines.append(f"\t\t{key} = {{")
    lines.extend(f"\t\t\t{field} = {value};" for field, value in fields.items())
    lines.append("\t\t};")
lines.extend(["\t};", f"\trootObject = {project};", "}"])
(PROJECT / "project.pbxproj").write_text("\n".join(lines) + "\n")

scheme_dir = PROJECT / "xcshareddata/xcschemes"
scheme_dir.mkdir(parents=True, exist_ok=True)


def reference(target, product, name):
    return (f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" '
            f'BuildableName="{product}" BlueprintName="{name}" ReferencedContainer="container:DualCam.xcodeproj"/>')


app_ref = reference(app, "DualCam.app", "DualCam")
test_ref = reference(tests, "DualCamTests.xctest", "DualCamTests")
(scheme_dir / "DualCam.xcscheme").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.7">
  <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES">
    <BuildActionEntries>
      <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{app_ref}</BuildActionEntry>
      <BuildActionEntry buildForTesting="YES" buildForRunning="NO" buildForProfiling="NO" buildForArchiving="NO" buildForAnalyzing="YES">{test_ref}</BuildActionEntry>
    </BuildActionEntries>
  </BuildAction>
  <TestAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="YES">
    <Testables><TestableReference skipped="NO">{test_ref}</TestableReference></Testables>
  </TestAction>
  <LaunchAction buildConfiguration="Debug" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugServiceExtension="internal" allowLocationSimulation="YES">
    <BuildableProductRunnable runnableDebuggingMode="0">{app_ref}</BuildableProductRunnable>
  </LaunchAction>
  <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES">
    <BuildableProductRunnable runnableDebuggingMode="0">{app_ref}</BuildableProductRunnable>
  </ProfileAction>
  <AnalyzeAction buildConfiguration="Debug"/>
  <ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''')
print(f"Generated {PROJECT.name}: {len(app_files)} app sources, {len(test_files)} test sources")
