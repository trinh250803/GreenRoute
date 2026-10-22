# Converts the HTML guide to Word with all screenshots embedded (needs Microsoft Word installed).
param([string]$Html = "$PSScriptRoot\GreenRoute_AI_Huong_dan_su_dung.html")
$docx = [IO.Path]::ChangeExtension($Html, ".docx")
$pdf = [IO.Path]::ChangeExtension($Html, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
  $doc = $word.Documents.Open($Html, $false, $true)
  foreach ($s in @($doc.InlineShapes)) {
    if ($s.LinkFormat) { $s.LinkFormat.SavePictureWithDocument = $true; $s.LinkFormat.BreakLink() }
  }
  $ps = $doc.PageSetup
  $ps.PaperSize = 7          # A4
  $ps.TopMargin = 56.7; $ps.BottomMargin = 56.7; $ps.LeftMargin = 56.7; $ps.RightMargin = 56.7   # 2 cm
  $doc.ActiveWindow.View.Type = 3   # print layout
  $doc.SaveAs2($docx, 16)
  $doc.SaveAs2($pdf, 17)
  "pages: " + $doc.ComputeStatistics(2) + "  images: " + $doc.InlineShapes.Count
  $doc.Close($false)
} finally { $word.Quit() }
"saved: $docx"
