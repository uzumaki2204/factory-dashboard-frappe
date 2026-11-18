param([string]$DotnetRoot = 'D:\Code\FactoryManagement')
$ErrorActionPreference = 'Stop'
$taskDirectory = Join-Path ([IO.Path]::GetTempPath()) ('dashboard-reference-' + [Guid]::NewGuid())
[IO.Directory]::CreateDirectory($taskDirectory) | Out-Null
$sourcePath = Join-Path $DotnetRoot 'src\FactoryManagement.Infrastructure\FactoryManagement.Infrastructure.csproj'
$escaped = [System.Security.SecurityElement]::Escape($sourcePath)
$project = '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><ProjectReference Include="' + $escaped + '" /></ItemGroup></Project>'
[IO.File]::WriteAllText((Join-Path $taskDirectory 'Reference.csproj'), $project, [Text.UTF8Encoding]::new($false))
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Program.cs') -Destination $taskDirectory
dotnet build (Join-Path $taskDirectory 'Reference.csproj') --verbosity quiet | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Reference build failed.' }
$result = dotnet (Join-Path $taskDirectory 'bin\Debug\net8.0\Reference.dll')
if ($LASTEXITCODE -ne 0) { throw 'Reference export failed.' }
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'dotnet.json'), ($result -join "`n"), [Text.UTF8Encoding]::new($false))
