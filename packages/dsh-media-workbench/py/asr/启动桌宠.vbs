' ????????????
' ????????????????

On Error Resume Next

Dim fso, shell, pyw, script
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

pyw = "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\pythonw.exe"
script = "E:\tools\asr\dsh-pet.py"

shell.Run """" & pyw & """ """ & script & """", 0, False
