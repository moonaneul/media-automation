set sourcePath to "/Users/moonaneul/Downloads/수요예배.pptx"
set destinationPath to "/Users/moonaneul/Documents/media-automation/output/mac_slide_merge_check.pptx"

tell application "Microsoft PowerPoint"
    activate

    open POSIX file sourcePath
    delay 1

    tell active window
        set view type to slide sorter view
    end tell

    select slide 22 of active presentation
end tell

tell application "System Events"
    keystroke "c" using command down
end tell

delay 1

tell application "Microsoft PowerPoint"
    close active presentation saving no
    delay 1

    open POSIX file destinationPath
    delay 1

    tell active window
        set view type to slide sorter view
    end tell

    select slide 1 of active presentation
end tell

tell application "System Events"
    keystroke "v" using command down
end tell

delay 2

tell application "Microsoft PowerPoint"
    set resultCount to count of slides of active presentation

    tell active window
        set view type to normal view
    end tell

    close active presentation saving yes

    return "slides=" & resultCount
end tell