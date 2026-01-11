import os
import xml.etree.ElementTree as ET
import time
import tarfile
import shutil
import json
import re
import subprocess
import hashlib
from xml.sax.saxutils import escape

def escape_xml(text):
    if text is None:
        return ""
    # Only escape if it's a string
    if not isinstance(text, str):
        text = str(text)
    return escape(text, entities={"'": "&apos;", "\"": "&quot;"})

# Templates for XML files (Refined to match sample exactly)
MOODLE_BACKUP_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<moodle_backup>
  <information>
    <name>{filename}</name>
    <moodle_version>2025100601.03</moodle_version>
    <moodle_release>5.1.1+ (Build: 20251219)</moodle_release>
    <backup_version>2025100600</backup_version>
    <backup_release>5.1</backup_release>
    <backup_date>{backup_date}</backup_date>
    <mnet_remoteusers>0</mnet_remoteusers>
    <include_files>1</include_files>
    <include_file_references_to_external_content>0</include_file_references_to_external_content>
    <original_wwwroot>https://www.ailearn.kr</original_wwwroot>
    <original_site_identifier_hash>a1b5b31080641851c531748a1b7258c7</original_site_identifier_hash>
    <original_course_id>1</original_course_id>
    <original_course_format>topics</original_course_format>
    <original_course_fullname>{course_fullname}</original_course_fullname>
    <original_course_shortname>{course_shortname}</original_course_shortname>
    <original_course_startdate>{startdate}</original_course_startdate>
    <original_course_enddate>{enddate}</original_course_enddate>
    <original_course_contextid>1</original_course_contextid>
    <original_system_contextid>1</original_system_contextid>
    <details>
      <detail backup_id="{backup_id}">
        <type>course</type>
        <format>moodle2</format>
        <interactive>1</interactive>
        <mode>70</mode>
        <execution>2</execution>
        <executiontime>0</executiontime>
      </detail>
    </details>
    <contents>
      <activities>
{activities}
      </activities>
      <sections>
{sections}
      </sections>
      <course>
        <courseid>1</courseid>
        <title>{course_fullname}</title>
        <directory>course</directory>
      </course>
    </contents>
    <settings>
      <setting>
        <level>root</level>
        <name>filename</name>
        <value>{filename}</value>
      </setting>
      <setting>
        <level>root</level>
        <name>users</name>
        <value>0</value>
      </setting>
      <setting>
        <level>root</level>
        <name>activities</name>
        <value>1</value>
      </setting>
      <setting>
        <level>root</level>
        <name>blocks</name>
        <value>0</value>
      </setting>
      <setting>
        <level>root</level>
        <name>files</name>
        <value>1</value>
      </setting>
{settings}
    </settings>
  </information>
</moodle_backup>
"""

ACTIVITY_ENTRY_TEMPLATE = """        <activity>
          <moduleid>{moduleid}</moduleid>
          <sectionid>{sectionid}</sectionid>
          <modulename>{modulename}</modulename>
          <title>{title}</title>
          <directory>activities/{modulename}_{moduleid}</directory>
          <insubsection></insubsection>
        </activity>"""

SECTION_ENTRY_TEMPLATE = """        <section>
          <sectionid>{sectionid}</sectionid>
          <title>{title}</title>
          <directory>sections/section_{sectionid}</directory>
          <parentcmid></parentcmid>
          <modname></modname>
        </section>"""

SETTING_ACTIVITY_TEMPLATE = """      <setting>
        <level>activity</level>
        <activity>{modulename}_{moduleid}</activity>
        <name>{modulename}_{moduleid}_included</name>
        <value>1</value>
      </setting>
      <setting>
        <level>activity</level>
        <activity>{modulename}_{moduleid}</activity>
        <name>{modulename}_{moduleid}_userinfo</name>
        <value>0</value>
      </setting>"""

SETTING_SECTION_TEMPLATE = """      <setting>
        <level>section</level>
        <section>section_{sectionid}</section>
        <name>section_{sectionid}_included</name>
        <value>1</value>
      </setting>
      <setting>
        <level>section</level>
        <section>section_{sectionid}</section>
        <name>section_{sectionid}_userinfo</name>
        <value>0</value>
      </setting>"""

COURSE_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<course id="1" contextid="1">
  <shortname>{course_shortname}</shortname>
  <fullname>{course_fullname}</fullname>
  <summary></summary>
  <summaryformat>1</summaryformat>
  <format>topics</format>
  <showgrades>1</showgrades>
  <startdate>{startdate}</startdate>
  <enddate>{enddate}</enddate>
  <visible>1</visible>
  <enablecompletion>1</enablecompletion>
</course>
"""

# Videowatch template including all tags from sample to prevent restore failure
VIDEOWATCH_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<activity id="{instanceid}" moduleid="{moduleid}" modulename="videowatch" contextid="{contextid}">
  <videowatch id="{instanceid}">
    <course>1</course>
    <name>{name}</name>
    <intro></intro>
    <introformat>1</introformat>
    <vimeo_url>{url}</vimeo_url>
    <video_description></video_description>
    <video_description_format>1</video_description_format>
    <timemodified>{timemodified}</timemodified>
    <completion_on_view_time>0</completion_on_view_time>
    <completion_on_view_time_second>$@NULL@$</completion_on_view_time_second>
    <completion_on_finish>0</completion_on_finish>
    <completion_on_percent>0</completion_on_percent>
    <completion_on_percent_value>0</completion_on_percent_value>
    <completion_hide_detail>0</completion_hide_detail>
    <viewpercentgrade>$@NULL@$</viewpercentgrade>
    <show_description_in_player>1</show_description_in_player>
    <enabletabs>0</enabletabs>
    <texttracks>
    </texttracks>
    <subplugin_videowatchtab_block_videowatch>
    </subplugin_videowatchtab_block_videowatch>
    <subplugin_videowatchtab_chapter_videowatch>
    </subplugin_videowatchtab_chapter_videowatch>
    <subplugin_videowatchtab_chat_videowatch>
    </subplugin_videowatchtab_chat_videowatch>
    <subplugin_videowatchtab_information_videowatch>
      <videowatchtab_information>
        <text></text>
        <format>1</format>
        <videowatch>{instanceid}</videowatch>
        <name></name>
      </videowatchtab_information>
    </subplugin_videowatchtab_information_videowatch>
    <subplugin_videowatchtab_related_videowatch>
    </subplugin_videowatchtab_related_videowatch>
    <subplugin_videowatchtab_texttrack_videowatch>
    </subplugin_videowatchtab_texttrack_videowatch>
    <subplugin_videowatchplugin_live_videowatch>
    </subplugin_videowatchplugin_live_videowatch>
    <subplugin_videowatchplugin_videojs_videowatch>
      <videojs_settings>
        <responsive>1</responsive>
        <autoplay>1</autoplay>
        <controls>1</controls>
        <muted>0</muted>
        <height>0</height>
        <option_loop>0</option_loop>
        <playsinline>1</playsinline>
        <speed>1</speed>
        <width>0</width>
      </videojs_settings>
    </subplugin_videowatchplugin_videojs_videowatch>
    <subplugin_videowatchplugin_vimeo_videowatch>
    </subplugin_videowatchplugin_vimeo_videowatch>
  </videowatch>
</activity>
"""

MODULE_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<module id="{moduleid}" version="2026010206">
  <modulename>videowatch</modulename>
  <sectionid>{sectionid}</sectionid>
  <sectionnumber>{sectionnumber}</sectionnumber>
  <idnumber></idnumber>
  <added>{timemodified}</added>
  <score>0</score>
  <indent>0</indent>
  <visible>1</visible>
  <visibleoncoursepage>1</visibleoncoursepage>
  <visibleold>1</visibleold>
  <groupmode>0</groupmode>
  <groupingid>0</groupingid>
  <completion>1</completion>
  <completiongradeitemnumber>$@NULL@$</completiongradeitemnumber>
  <completionpassgrade>0</completionpassgrade>
  <completionview>0</completionview>
  <completionexpected>0</completionexpected>
  <availability>$@NULL@$</availability>
  <showdescription>0</showdescription>
  <downloadcontent>1</downloadcontent>
  <lang></lang>
  <enableaitools>$@NULL@$</enableaitools>
  <enabledaiactions>$@NULL@$</enabledaiactions>
  <tags>
  </tags>
</module>
"""

SECTION_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<section id="{sectionid}">
  <number>{number}</number>
  <name>{name}</name>
  <summary></summary>
  <summaryformat>1</summaryformat>
  <sequence>{sequence}</sequence>
  <visible>1</visible>
  <availabilityjson>$@NULL@$</availabilityjson>
  <component>$@NULL@$</component>
  <itemid>$@NULL@$</itemid>
  <timemodified>{timemodified}</timemodified>
</section>
"""

def extract_playlist_info(url, start_index=None, end_index=None):
    """
    Extracts video URLs and titles from a YouTube playlist using yt-dlp.
    """
    print(f"Fetching playlist info from {url}...")
    
    command = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
    ]
    
    if start_index:
        command.extend(["--playlist-start", str(start_index)])
    if end_index:
        command.extend(["--playlist-end", str(end_index)])
        
    command.append(url)
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        entries = data.get("entries", [])
        videos = []
        for entry in entries:
            title = entry.get("title", "Unknown Title")
            # Construct clean URL
            video_id = entry.get("id")
            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get("url")
            if title and video_url:
                videos.append({
                    'title': title,
                    'url': video_url
                })
        return videos
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed: {e.stderr}")
        # Fallback for single video if it's not a playlist
        if "watch?v=" in url:
             video_id = url.split("watch?v=")[1].split("&")[0]
             return [{'title': 'Video', 'url': f'https://www.youtube.com/watch?v={video_id}'}]
        return []
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return []

class MoodleCourseCreator:
    def __init__(self, course_name, videos):
        self.course_fullname = escape_xml(course_name)
        self.course_shortname = escape_xml(course_name[:10])
        self.videos = videos
        self.backup_date = int(time.time())
        self.backup_id = hashlib.md5(str(self.backup_date).encode()).hexdigest()
        self.output_dir = "generated_backup"
        self.filename = f"backup-generated-{self.backup_date}.mbz"

    def create_structure(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(os.path.join(self.output_dir, "activities"))
        os.makedirs(os.path.join(self.output_dir, "sections"))
        os.makedirs(os.path.join(self.output_dir, "course"))

        activities_xml = []
        sections_xml = []
        settings_xml = []

        # Add Section 0 (General)
        section0_id = 10
        self.write_xml(os.path.join(self.output_dir, "sections", f"section_{section0_id}", "section.xml"),
                       SECTION_XML_TEMPLATE.format(sectionid=section0_id, number=0, name="", sequence="", timemodified=self.backup_date))
        self.write_xml(os.path.join(self.output_dir, "sections", f"section_{section0_id}", "inforef.xml"), '<?xml version="1.0" encoding="UTF-8"?><inforef></inforef>')
        
        sections_xml.append(SECTION_ENTRY_TEMPLATE.format(sectionid=section0_id, title="0"))
        settings_xml.append(SETTING_SECTION_TEMPLATE.format(sectionid=section0_id))

        for i, video in enumerate(self.videos):
            num = i + 1
            # In the sample, sectionid and moduleid match.
            section_id = 100 + num
            module_id = 100 + num
            instance_id = 1000 + num
            context_id = 10000 + num

            # Create Activity Directory
            act_dir = os.path.join(self.output_dir, "activities", f"videowatch_{module_id}")
            os.makedirs(act_dir)
            
            video_title_escaped = escape_xml(video['title'])
            video_url_escaped = escape_xml(video['url'])

            self.write_xml(os.path.join(act_dir, "videowatch.xml"),
                           VIDEOWATCH_XML_TEMPLATE.format(instanceid=instance_id, moduleid=module_id, contextid=context_id, name=video_title_escaped, url=video_url_escaped, timemodified=self.backup_date))
            
            self.write_xml(os.path.join(act_dir, "module.xml"),
                           MODULE_XML_TEMPLATE.format(moduleid=module_id, sectionid=section_id, sectionnumber=num, timemodified=self.backup_date))
            
            for f in ["roles.xml", "grades.xml", "grade_history.xml", "inforef.xml"]:
                self.write_xml(os.path.join(act_dir, f), '<?xml version="1.0" encoding="UTF-8"?><root></root>' if "history" in f else '<?xml version="1.0" encoding="UTF-8"?><{0}></{0}>'.format(f.split('.')[0]))

            # Create Section Directory
            sec_dir = os.path.join(self.output_dir, "sections", f"section_{section_id}")
            os.makedirs(sec_dir, exist_ok=True)
            self.write_xml(os.path.join(sec_dir, "section.xml"),
                           SECTION_XML_TEMPLATE.format(sectionid=section_id, number=num, name=f"{num}. {video_title_escaped}", sequence=module_id, timemodified=self.backup_date))
            self.write_xml(os.path.join(sec_dir, "inforef.xml"), '<?xml version="1.0" encoding="UTF-8"?><inforef></inforef>')

            activities_xml.append(ACTIVITY_ENTRY_TEMPLATE.format(moduleid=module_id, sectionid=section_id, modulename="videowatch", title=video_title_escaped))
            sections_xml.append(SECTION_ENTRY_TEMPLATE.format(sectionid=section_id, title=f"{num}. {video_title_escaped}"))
            settings_xml.append(SETTING_ACTIVITY_TEMPLATE.format(modulename="videowatch", moduleid=module_id))
            settings_xml.append(SETTING_SECTION_TEMPLATE.format(sectionid=section_id))

        self.write_xml(os.path.join(self.output_dir, "moodle_backup.xml"),
                       MOODLE_BACKUP_XML_TEMPLATE.format(filename=self.filename, backup_date=self.backup_date, backup_id=self.backup_id, course_fullname=self.course_fullname, course_shortname=self.course_shortname, startdate=self.backup_date, enddate=self.backup_date+31536000, activities="\n".join(activities_xml), sections="\n".join(sections_xml), settings="\n".join(settings_xml)))
        
        self.write_xml(os.path.join(self.output_dir, "course", "course.xml"),
                       COURSE_XML_TEMPLATE.format(course_fullname=self.course_fullname, course_shortname=self.course_shortname, startdate=self.backup_date, enddate=self.backup_date+31536000))

        for f in ["files.xml", "questions.xml", "groups.xml", "gradebook.xml", "outcomes.xml", "scales.xml", "roles.xml", "completion.xml"]:
             self.write_xml(os.path.join(self.output_dir, f), '<?xml version="1.0" encoding="UTF-8"?><{0}></{0}>'.format(f.split('.')[0]))
        
        self.write_xml(os.path.join(self.output_dir, "course", "enrolments.xml"), '<?xml version="1.0" encoding="UTF-8"?><enrolments></enrolments>')
        self.write_xml(os.path.join(self.output_dir, "course", "roles.xml"), '<?xml version="1.0" encoding="UTF-8"?><roles></roles>')
        self.write_xml(os.path.join(self.output_dir, "course", "inforef.xml"), '<?xml version="1.0" encoding="UTF-8"?><inforef></inforef>')
        self.write_xml(os.path.join(self.output_dir, "course", "completiondefaults.xml"), '<?xml version="1.0" encoding="UTF-8"?><completiondefaults></completiondefaults>')
        self.write_xml(os.path.join(self.output_dir, "grade_history.xml"), '<?xml version="1.0" encoding="UTF-8"?><grade_history></grade_history>')
        self.write_xml(os.path.join(self.output_dir, "moodle_backup.log"), "")

    def write_xml(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def package(self):
        print(f"Packaging {self.filename}...")
        with tarfile.open(self.filename, "w:gz") as tar:
            for item in sorted(os.listdir(self.output_dir)):
                tar.add(os.path.join(self.output_dir, item), arcname=item)
        print(f"Successfully created {self.filename}")

if __name__ == "__main__":
    import sys
    
    url = None
    start = None
    end = None
    
    if os.path.exists("source.txt"):
        with open("source.txt", "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            if lines:
                url = lines[0]
                # Optional range in source.txt: line 2 = start, line 3 = end
                if len(lines) >= 2:
                    try: start = int(lines[1])
                    except: pass
                if len(lines) >= 3:
                    try: end = int(lines[2])
                    except: pass
    
    # Overwrite with command line args if provided: python script.py <url> <start> <end>
    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 3:
        try:
            start = int(sys.argv[2])
            end = int(sys.argv[3])
        except: pass
        
    if not url:
        print("Usage: python moodle_course_creator.py <playlist_url> [start_index] [end_index]")
        print("Or provide a source.txt file with the URL on the first line.")
        exit(1)
        
    videos = extract_playlist_info(url, start, end)
    
    if not videos:
        print("No videos found!")
        exit(1)
        
    creator = MoodleCourseCreator("Generated Course", videos)
    creator.create_structure()
    creator.package()
    
    # Cleanup obsolete files if they exist
    for f in ['playlist.html', 'ref_files.txt', 'gen_files.txt']:
        if os.path.exists(f):
            os.remove(f)
