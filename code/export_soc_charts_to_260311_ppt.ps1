param(
    [string]$ExcelPath = "",
    [string]$PptPath = "",
    [int]$MaxChartsPerSlide = 13,
    [string]$OutputPptPath = ""
)

$baseDir = Join-Path $env:USERPROFILE "OneDrive"
$excelPattern = "*xmeans_daytrend_seed42_kmax50*.xlsx"

if ([string]::IsNullOrWhiteSpace($ExcelPath)) {
    Write-Output "INFO: Searching latest xmeans result xlsx under $baseDir"
    $excelCandidates = Get-ChildItem -Path $baseDir -Recurse -File -Filter $excelPattern -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "x-means_" } |
        Sort-Object LastWriteTime -Descending
    if (-not $excelCandidates) {
        throw "Excel file not found: $excelPattern"
    }
    $ExcelPath = $excelCandidates[0].FullName
}

if ([string]::IsNullOrWhiteSpace($PptPath)) {
    Write-Output "INFO: Searching latest 260311.pptx under $baseDir"
    $pptCandidates = Get-ChildItem -Path $baseDir -Recurse -File -Filter "260311.pptx" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    if (-not $pptCandidates) {
        throw "PPTX not found: 260311.pptx"
    }
    $PptPath = $pptCandidates[0].FullName
}

if (-not (Test-Path -LiteralPath $PptPath)) {
    throw "PPTX not found: $PptPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputPptPath)) {
    $outputDir = Split-Path -Parent $PptPath
    if ([string]::IsNullOrWhiteSpace($outputDir)) { $outputDir = Get-Location }
    $outputBase = [System.IO.Path]::GetFileNameWithoutExtension($PptPath)
    $outputExt = [System.IO.Path]::GetExtension($PptPath)
    $OutputPptPath = Join-Path $outputDir ("{0}_{1}{2}" -f $outputBase, $timestamp, $outputExt)
}

if ($OutputPptPath -eq $PptPath) {
    throw "OutputPptPath must be different from input PptPath to avoid overwriting."
}
if (-not (Test-Path -LiteralPath (Split-Path -Parent $OutputPptPath))) {
    throw "Output directory not found: $OutputPptPath"
}
Copy-Item -LiteralPath $PptPath -Destination $OutputPptPath -Force

$tempDir = Join-Path $env:TEMP "soc_chart_export"
if (-not (Test-Path -LiteralPath $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}

function Get-CellDouble([__ComObject]$Worksheet, [int]$Row, [int]$Column) {
    try {
        $val = $Worksheet.Cells.Item($Row, $Column).Value2
        if ($null -eq $val) { return 0.0 }
        return [double]$val
    } catch {
        return 0.0
    }
}

function Get-SectionRange([__ComObject]$Worksheet, [int]$SectionHeaderRow, [int]$MaxRow) {
    if ($SectionHeaderRow -le 0 -or $SectionHeaderRow -ge $MaxRow) { return $null }

    $start = $SectionHeaderRow + 2
    $end = $start
    while ($end -le $MaxRow) {
        $step = [string]$Worksheet.Cells.Item($end, 1).Text
        $step = $step.Trim()
        if (-not [string]::IsNullOrWhiteSpace($step) -and $step -match '^(t\d{1,2}|\d{1,2})$') {
            $end++
            continue
        }
        break
    }
    $end = [Math]::Max($end - 1, $start - 1)
    if ($start -gt $end) { return $null }
    return @{ Start = $start; End = $end }
}

function Get-DiffSummary([__ComObject]$Worksheet, [hashtable]$Range, [int]$ColA, [int]$ColB) {
    $start = [int]$Range.Start
    $end = [int]$Range.End
    $count = 0
    $sumA = 0.0
    $sumB = 0.0

    for ($r = $start; $r -le $end; $r++) {
        $sumA += Get-CellDouble -Worksheet $Worksheet -Row $r -Column $ColA
        $sumB += Get-CellDouble -Worksheet $Worksheet -Row $r -Column $ColB
        $count++
    }
    if ($count -eq 0) { return $null }

    return @{
        AvgDiff = (($sumA - $sumB) / $count)
        SumDiff = ($sumA - $sumB)
    }
}

function Format-Diff([string]$Label, [double]$AvgDiff, [double]$SumDiff) {
    if ([Math]::Abs($SumDiff) -lt 0.0005) {
        return ("{0}: almost same (avg diff {1:F3}, sum diff {2:F2})" -f $Label, $AvgDiff, $SumDiff)
    }
    if ($SumDiff -gt 0) {
        return ("{0}: degraded case is higher (avg diff {1:F3}, sum diff {2:F2})" -f $Label, $AvgDiff, $SumDiff)
    }
    return ("{0}: non-degraded case is higher (avg diff {1:F3}, sum diff {2:F2})" -f $Label, $AvgDiff, $SumDiff)
}

function Get-DateLabel([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    $match = [regex]::Match($Text, '(\d{4})[\\/._-]?([0-9]{1,2})[\\/._-]?([0-9]{1,2})')
    if ($match.Success) {
        $y = [int]$match.Groups[1].Value
        $m = [int]$match.Groups[2].Value
        $d = [int]$match.Groups[3].Value
        if ($m -ge 1 -and $m -le 12 -and $d -ge 1 -and $d -le 31) {
            return ("{0:D4}-{1:D2}-{2:D2}" -f $y, $m, $d)
        }
    }
    return ""
}

function Get-DateString([object]$Value) {
    if ($null -eq $Value) { return "" }

    if ($Value -is [DateTime]) {
        return $Value.ToString("yyyy-MM-dd")
    }

    if ($Value -is [double]) {
        try {
            return [DateTime]::FromOADate([double]$Value).ToString("yyyy-MM-dd")
        } catch {
            return ""
        }
    }

    $text = [string]$Value
    $text = $text.Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return "" }

    $m = [regex]::Match($text, "(\d{4})[\\/._-]?([0-9]{1,2})[\\/._-]?([0-9]{1,2})")
    if ($m.Success) {
        try {
            return ("{0:D4}-{1:D2}-{2:D2}" -f [int]$m.Groups[1].Value, [int]$m.Groups[2].Value, [int]$m.Groups[3].Value)
        } catch {}
    }

    try {
        $parsed = [DateTime]::Parse($text)
        return $parsed.ToString("yyyy-MM-dd")
    } catch {
        return ""
    }
}

function Get-ChartDateSummary([__ComObject]$Chart, [__ComObject]$Workbook) {
    $seriesCollection = $Chart.SeriesCollection()
    if ($seriesCollection.Count -eq 0) {
        return "dates: -"
    }

    $dateSet = New-Object System.Collections.Generic.List[string]
    $dates = New-Object System.Collections.Generic.HashSet[string]

    for ($i = 1; $i -le $seriesCollection.Count; $i++) {
        $series = $seriesCollection.Item($i)
        $formula = ""
        try { $formula = [string]$series.Formula } catch {}
        if ([string]::IsNullOrWhiteSpace($formula)) { continue }

        $matches = [regex]::Matches($formula, "'[^']+'!\$[A-Z]+\$\d+:\$[A-Z]+\$\d+")
        if ($matches.Count -lt 2) { continue }

        $ref = $matches[1].Value
        $bang = $ref.IndexOf('!')
        if ($bang -le 0) { continue }
        $sheetName = $ref.Substring(0, $bang).Trim("'")
        $rowMatch = [regex]::Match($ref, '\$(?<col>[A-Z]+)\$(?<row>\d+)')
        if (-not $rowMatch.Success) { continue }
        $row = [int]$rowMatch.Groups["row"].Value

        try {
            $sheet = $Workbook.Worksheets.Item($sheetName)
            $rawDate = $sheet.Cells.Item($row, 2).Value2
            $dateText = Get-DateString -Value $rawDate
            if ([string]::IsNullOrWhiteSpace($dateText)) { continue }
            if (-not $dates.Contains($dateText)) {
                [void]$dates.Add($dateText)
            }
        } catch {
            continue
        }
    }

    if ($dates.Count -eq 0) {
        return "dates: -"
    }

    $sorted = @($dates)
    $sorted = $sorted | Sort-Object
    if ($sorted.Count -le 4) {
        return "dates: " + ($sorted -join ", ")
    }

    $start = $sorted[0]
    $end = $sorted[-1]
    return "dates: $start - $end (n=$($sorted.Count))"
}

function Get-ChartText([__ComObject]$Chart) {
    try {
        if ($Chart.HasTitle -and $Chart.ChartTitle -and -not [string]::IsNullOrWhiteSpace([string]$Chart.ChartTitle.Text)) {
            return [string]$Chart.ChartTitle.Text
        }
    } catch {
        return ""
    }
    return ""
}

function Get-ChartClusterId([__ComObject]$Chart, [int]$FallbackIndex) {
    $title = Get-ChartText -Chart $Chart
    $m = [regex]::Match($title, 'Cluster\s*([0-9]+)')
    if ($m.Success) {
        try { return [int]$m.Groups[1].Value } catch {}
    }
    $n = [regex]::Match($title, '([0-9]+)')
    if ($n.Success) {
        try { return [int]$n.Groups[1].Value } catch {}
    }
    return $FallbackIndex
}

function Build-RepresentativeDateMap([__ComObject]$Workbook) {
    $map = @{}
    foreach ($ws in $Workbook.Worksheets) {
        if (-not ($ws.Name -like "*_repr")) { continue }
        $base = $ws.Name -replace "_repr$",""
        $lastRow = [int]$ws.UsedRange.Rows.Count
        if ($lastRow -lt 2) { continue }
        for ($r = 2; $r -le $lastRow; $r++) {
            $clusterRaw = $ws.Cells.Item($r, 2).Value2
            if ($null -eq $clusterRaw) { continue }
            try {
                $cluster = [int][double]$clusterRaw
            } catch {
                try {
                    $cluster = [int]$clusterRaw
                } catch {
                    continue
                }
            }
            $dateRaw = $ws.Cells.Item($r, 3).Value2
            $dateText = Get-DateString -Value $dateRaw
            if ([string]::IsNullOrWhiteSpace($dateText)) { continue }
            $map["$base|$cluster"] = $dateText
        }
    }
    return $map
}

function Get-SlideInsight([__ComObject]$Worksheet, [int]$LastRow, [hashtable]$SectionRows) {
    $items = New-Object System.Collections.Generic.List[string]

    if ($SectionRows.ContainsKey('SOC') -and $SectionRows.SOC -gt 0) {
        $soc = Get-SectionRange -Worksheet $Worksheet -SectionHeaderRow $SectionRows.SOC -MaxRow $LastRow
        if ($soc -ne $null) {
            $s = Get-DiffSummary -Worksheet $Worksheet -Range $soc -ColA 2 -ColB 3
            if ($s -ne $null) {
                $items.Add((Format-Diff -Label 'SOC' -AvgDiff $s.AvgDiff -SumDiff $s.SumDiff))
            }
        }
    }

    if ($SectionRows.ContainsKey('Spot') -and $SectionRows.Spot -gt 0) {
        $spot = Get-SectionRange -Worksheet $Worksheet -SectionHeaderRow $SectionRows.Spot -MaxRow $LastRow
        if ($spot -ne $null) {
            $buy = Get-DiffSummary -Worksheet $Worksheet -Range $spot -ColA 2 -ColB 3
            if ($buy -ne $null) { $items.Add((Format-Diff -Label 'Spot buy' -AvgDiff $buy.AvgDiff -SumDiff $buy.SumDiff)) }
            $sell = Get-DiffSummary -Worksheet $Worksheet -Range $spot -ColA 5 -ColB 6
            if ($sell -ne $null) { $items.Add((Format-Diff -Label 'Spot sell' -AvgDiff $sell.AvgDiff -SumDiff $sell.SumDiff)) }
        }
    }

    if ($SectionRows.ContainsKey('PS') -and $SectionRows.PS -gt 0) {
        $ps = Get-SectionRange -Worksheet $Worksheet -SectionHeaderRow $SectionRows.PS -MaxRow $LastRow
        if ($ps -ne $null) {
            $p1 = Get-DiffSummary -Worksheet $Worksheet -Range $ps -ColA 2 -ColB 3
            if ($p1 -ne $null) { $items.Add((Format-Diff -Label 'Primary' -AvgDiff $p1.AvgDiff -SumDiff $p1.SumDiff)) }
            $p2 = Get-DiffSummary -Worksheet $Worksheet -Range $ps -ColA 5 -ColB 6
            if ($p2 -ne $null) { $items.Add((Format-Diff -Label 'Secondary' -AvgDiff $p2.AvgDiff -SumDiff $p2.SumDiff)) }
        }
    }

    if ($items.Count -eq 0) {
        return 'Could not extract metrics to generate a short insight.'
    }
    return ($items | Select-Object -First 4) -join ' | '
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = 1

try {
    try {
        $wb = $excel.Workbooks.Open($ExcelPath, 0, $true)
    } catch {
        Write-Output "INFO: Input workbook is locked. Using temporary copy."
        $workbookCopy = Join-Path $tempDir ("metrics_copy_{0}.xlsx" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
        Copy-Item -LiteralPath $ExcelPath -Destination $workbookCopy -Force
        $wb = $excel.Workbooks.Open($workbookCopy, 0, $true)
        $CopiedWorkbookPath = $workbookCopy
    }

    try {
        $pres = $ppt.Presentations.Open($OutputPptPath, $false, $false, $true)
    } catch {
        throw "Failed to open PowerPoint: $OutputPptPath"
    }
    $beforeSlideCount = [int]$pres.Slides.Count

    $blankLayout = 12
    $chartCount = 0
    $addedCount = 0
    $reprDateMap = Build-RepresentativeDateMap -Workbook $wb

    foreach ($ws in $wb.Worksheets) {
        if ($ws.Name -eq 'index') { continue }

        $lastRow = [int]$ws.UsedRange.Rows.Count
        $chartObjects = @($ws.ChartObjects()) | Sort-Object -Property Top, Left
        if ($chartObjects.Count -eq 0) { continue }

        $sectionRows = @{
            SOC = 5
            Spot = 57
            PS = 108
        }
        $insightText = Get-SlideInsight -Worksheet $ws -LastRow $lastRow -SectionRows $sectionRows
        $processed = 0
        foreach ($co in $chartObjects) {
            if ($processed -ge $MaxChartsPerSlide) { break }

            $chartCount++
            $imgPath = Join-Path $tempDir ("soc_chart_{0:D4}.png" -f $chartCount)
            $co.Chart.Export($imgPath, "PNG") | Out-Null
            if (-not (Test-Path -LiteralPath $imgPath)) {
                Write-Warning "Export failed: $imgPath"
                continue
            }

            $slide = $pres.Slides.Add($pres.Slides.Count + 1, $blankLayout)
            $dateFromSheet = Get-DateLabel $ws.Name
            $baseName = $ws.Name -replace '_soc$',''
            $clusterId = Get-ChartClusterId -Chart $co.Chart -FallbackIndex $processed
            $repDateKey = "$baseName|$clusterId"
            $representativeDate = ""
            if ($reprDateMap.ContainsKey($repDateKey)) {
                $representativeDate = $reprDateMap[$repDateKey]
            }
            $dateFromSeries = Get-ChartDateSummary -Chart $co.Chart -Workbook $wb
            if ([string]::IsNullOrWhiteSpace($representativeDate)) {
                if ([string]::IsNullOrWhiteSpace($dateFromSheet) -and ($dateFromSeries -ne "dates: -")) {
                    $dateFromSheet = $dateFromSeries
                } elseif (-not [string]::IsNullOrWhiteSpace($dateFromSeries) -and ($dateFromSeries -ne "dates: -")) {
                    $dateFromSheet = $dateFromSheet + " / " + $dateFromSeries
                }
            } else {
                $dateFromSheet = "代表日: $representativeDate"
            }
            if ([string]::IsNullOrWhiteSpace($dateFromSheet)) {
                try {
                    $dateFromChart = Get-DateLabel ([string]$co.Chart.ChartTitle.Text)
                } catch {
                    $dateFromChart = ""
                }
                $dateFromSheet = $dateFromChart
            }

            $slideTitle = $ws.Name
            if (-not [string]::IsNullOrWhiteSpace($dateFromSheet)) {
                $slideTitle = ("{0} ({1})" -f $slideTitle, $dateFromSheet)
            }

            $title = $slide.Shapes.AddTextbox(1, 20, 10, 680, 24)
            $title.TextFrame.TextRange.Text = $slideTitle
            $title.TextFrame.TextRange.Font.Size = 16

            $chartTag = Get-ChartText -Chart $co.Chart
            if ([string]::IsNullOrWhiteSpace($chartTag)) {
                $chartTag = ('Chart ' + ($processed + 1))
            }
            $dateLabel = if ([string]::IsNullOrWhiteSpace($dateFromSheet)) { '' } else { "$dateFromSheet`r`n" }

            $slideWidth = [int]$pres.PageSetup.SlideWidth
            $slideHeight = [int]$pres.PageSetup.SlideHeight
            $marginX = 20
            $marginY = 52
            $titleHeight = 34
            $insightHeight = 70
            $chartWidth = $slideWidth - 2 * $marginX
            $chartHeight = $slideHeight - $marginY - $titleHeight - $insightHeight - 24
            if ($chartHeight -lt 200) { $chartHeight = 200 }

            $slide.Shapes.AddPicture($imgPath, $false, $true, $marginX, $marginY + $titleHeight, $chartWidth, $chartHeight) | Out-Null

            $insightTop = $slideHeight - $insightHeight - 10
            $insightBox = $slide.Shapes.AddTextbox(1, $marginX, $insightTop, $slideWidth - (2 * $marginX), $insightHeight)
            $insightBox.TextFrame.TextRange.Text = "$($dateLabel)$($chartTag)`r`n$insightText"
            $insightBox.TextFrame.TextRange.Font.Size = 12
            $addedCount++
            $processed++
        }
    }

    $pres.Save()
    $afterSlideCount = [int]$pres.Slides.Count
    Write-Output "beforeSlides=$beforeSlideCount"
    Write-Output "excel=$ExcelPath"
    Write-Output "inserted=$addedCount"
    Write-Output "afterSlides=$afterSlideCount"
    Write-Output "ppt=$OutputPptPath"
} finally {
    if ($wb) { $wb.Close($false) | Out-Null }
    if ($pres) { $pres.Close() | Out-Null }
    if ($excel) { $excel.Quit() | Out-Null }
    if ($ppt) { $ppt.Quit() | Out-Null }

    if ($CopiedWorkbookPath) {
        Remove-Item -LiteralPath $CopiedWorkbookPath -ErrorAction SilentlyContinue
    }
    Remove-Item -Path (Join-Path $tempDir "soc_chart_*.png") -ErrorAction SilentlyContinue
    Remove-Item -Path (Join-Path $tempDir "metrics_copy_*.xlsx") -ErrorAction SilentlyContinue
}

