param(
    [string]$InputPath = "",
    [string]$TemplatePath = "",
    [string]$OutputPath = "",
    [switch]$OverwriteGeneratedCharts
)

if ([string]::IsNullOrWhiteSpace($InputPath)) {
    $InputPath = Join-Path $env:USERPROFILE "OneDrive\研究\result\2d_piecewise_batch_2_20260306_161151\c01_13days_metrics_deg_vs_nodeg_by_repdate.xlsx"
}

if ([string]::IsNullOrWhiteSpace($TemplatePath)) {
    $TemplatePath = Join-Path $env:USERPROFILE "OneDrive\研究\260302\グラフ 1.crtx"
}

function Get-ColumnLetter([int]$ColumnNumber) {
    $result = ""
    $n = $ColumnNumber
    while ($n -gt 0) {
        $n--
        $result = [char](65 + ($n % 26)) + $result
        $n = [Math]::Floor($n / 26)
    }
    return $result
}

function Get-SectionEndRow([__ComObject]$Worksheet, [int]$StartRow, [int]$MaxRow) {
    $r = $StartRow
    while ($r -le $MaxRow) {
        $step = [string]$Worksheet.Cells.Item($r, 1).Text
        $step = $step.Trim()
        if (-not [string]::IsNullOrWhiteSpace($step) -and $step -match '^(t\d{1,2}|\d{1,2})$') {
            $r++
            continue
        }
        break
    }
    return [Math]::Max($r - 1, $StartRow - 1)
}

function Add-CompareLineChart(
    [__ComObject]$Worksheet,
    [string]$Title,
    [int]$HeaderRow,
    [int]$DataStartRow,
    [int]$DataEndRow,
    [int[]]$SeriesColumns,
    [int]$Left,
    [int]$Top,
    [int]$Width,
    [int]$Height,
    [string]$TemplatePath
) {
    if ($DataEndRow -lt $DataStartRow) {
        return
    }

    $start = [int]$DataStartRow
    $end = [int]$DataEndRow
    if ($start -gt $end) {
        return
    }

    $safeTitle = ($Title -replace '[\\/:*?"<>|]', '_')
    $chartObj = $Worksheet.ChartObjects().Add($Left, $Top, $Width, $Height)
    $chartObj.Name = "cmp_metric_{0}" -f $safeTitle
    $chart = $chartObj.Chart
    $chart.ChartType = 4  # xlLine

    if (Test-Path -LiteralPath $TemplatePath) {
        $chart.ApplyChartTemplate($TemplatePath) | Out-Null
    }

    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title

    $xValues = $Worksheet.Range(("A{0}:A{1}" -f $start, $end))

    $seriesCollection = $chart.SeriesCollection()
    for ($i = $seriesCollection.Count; $i -ge 1; $i--) {
        $seriesCollection.Item($i).Delete() | Out-Null
    }

    foreach ($col in $SeriesColumns) {
        $colLetter = Get-ColumnLetter $col
        $name = [string]$Worksheet.Cells.Item($HeaderRow, $col).Text
        $values = $Worksheet.Range(("{0}{1}:{0}{2}" -f $colLetter, $start, $end))

        $series = $chart.SeriesCollection().NewSeries()
        $series.Name = $name
        $series.Values = $values
        $series.XValues = $xValues
    }

    $chart.HasLegend = $true
    try {
        $chart.Legend.Position = -4152  # xlLegendPositionRight
    } catch {
        $chart.Legend.Position = 2  # default fallback
    }
}

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Input file not found: $InputPath"
}
if (-not (Test-Path -LiteralPath $TemplatePath)) {
    throw "Template file not found: $TemplatePath"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $InputDir = Split-Path -Path $InputPath -Parent
    $InputFile = Split-Path -Leaf $InputPath
    $OutputPath = Join-Path $InputDir ($InputFile -replace '\.xlsx$', '_with_charts.xlsx')
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    $wb = $excel.Workbooks.Open($InputPath)
    foreach ($ws in $wb.Worksheets) {
        if ($ws.Name -eq 'index') { continue }

        if ($OverwriteGeneratedCharts) {
            $oldCharts = $ws.ChartObjects()
            for ($i = $oldCharts.Count; $i -ge 1; $i--) {
                $name = [string]$oldCharts.Item($i).Name
                if ($name -like 'cmp_metric_*') {
                    $oldCharts.Item($i).Delete() | Out-Null
                }
            }
        }

        $lastRow = [int]$ws.UsedRange.Rows.Count
        $socRow = 0
        $spotRow = 0
        $psRow = 0

        for ($r = 1; $r -le $lastRow; $r++) {
            $label = [string]$ws.Cells.Item($r, 1).Text
            if ([string]::IsNullOrWhiteSpace($label)) {
                continue
            }
            $label = $label.Trim()
            if ($label -eq 'SOC推移') {
                $socRow = $r
            } elseif ($label -eq 'spot売買量') {
                $spotRow = $r
            } elseif ($label -eq '一次・二次売電量') {
                $psRow = $r
            }
        }

        if ($socRow -gt 0) {
            $socHeader = $socRow + 1
            $socStart = $socHeader + 1
            $socEnd = Get-SectionEndRow -Worksheet $ws -StartRow $socStart -MaxRow $lastRow
            Add-CompareLineChart -Worksheet $ws -Title 'SOC (degradation / no-degradation)' -HeaderRow $socHeader -DataStartRow $socStart -DataEndRow $socEnd -SeriesColumns @(2,3) -Left 20 -Top 20 -Width 500 -Height 180 -TemplatePath $TemplatePath
        }

        if ($spotRow -gt 0) {
            $spotHeader = $spotRow + 1
            $spotStart = $spotHeader + 1
            $spotEnd = Get-SectionEndRow -Worksheet $ws -StartRow $spotStart -MaxRow $lastRow
            Add-CompareLineChart -Worksheet $ws -Title 'spot buy (degradation / no-degradation)' -HeaderRow $spotHeader -DataStartRow $spotStart -DataEndRow $spotEnd -SeriesColumns @(2,3) -Left 20 -Top 215 -Width 500 -Height 180 -TemplatePath $TemplatePath
            Add-CompareLineChart -Worksheet $ws -Title 'spot sell (degradation / no-degradation)' -HeaderRow $spotHeader -DataStartRow $spotStart -DataEndRow $spotEnd -SeriesColumns @(5,6) -Left 540 -Top 215 -Width 500 -Height 180 -TemplatePath $TemplatePath
        }

        if ($psRow -gt 0) {
            $psHeader = $psRow + 1
            $psStart = $psHeader + 1
            $psEnd = Get-SectionEndRow -Worksheet $ws -StartRow $psStart -MaxRow $lastRow
            Add-CompareLineChart -Worksheet $ws -Title 'primary (degradation / no-degradation)' -HeaderRow $psHeader -DataStartRow $psStart -DataEndRow $psEnd -SeriesColumns @(2,3) -Left 20 -Top 410 -Width 500 -Height 180 -TemplatePath $TemplatePath
            Add-CompareLineChart -Worksheet $ws -Title 'secondary (degradation / no-degradation)' -HeaderRow $psHeader -DataStartRow $psStart -DataEndRow $psEnd -SeriesColumns @(5,6) -Left 540 -Top 410 -Width 500 -Height 180 -TemplatePath $TemplatePath
        }
    }

    if (Test-Path -LiteralPath $OutputPath) {
        Remove-Item -LiteralPath $OutputPath -Force | Out-Null
    }
    try {
        $wb.SaveAs($OutputPath, 51) | Out-Null
    } catch {
        $wb.SaveCopyAs($OutputPath)
    }
    Write-Output "output=$OutputPath"
} finally {
    if ($wb) { $wb.Close($true) | Out-Null }
    if ($excel) { $excel.Quit() | Out-Null }
    [Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
}
