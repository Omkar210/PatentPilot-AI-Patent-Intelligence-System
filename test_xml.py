import xml.etree.ElementTree as ET
xml_str = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test</title></entry></feed>'''
root = ET.fromstring(xml_str)
print(root.findall('atom:entry', {'atom': 'http://www.w3.org/2005/Atom'}))
