using System.IO;
using System.Text;
using System.Xml;
using System.Xml.Serialization;

namespace nvidiaProfileInspector.Common.Helper
{
    public static class XMLHelper<T> where T : new()
    {
        static XmlSerializer xmlSerializer;

        static XMLHelper()
        {
            xmlSerializer = new XmlSerializer(typeof(T));
        }

        public static string SerializeToXmlString(T xmlObject, Encoding encoding, bool removeNamespace)
        {
            var memoryStream = new MemoryStream();
            var xmlWriter = new XmlTextWriter(memoryStream, encoding) { Formatting = Formatting.Indented };

            if (removeNamespace)
            {
                var xs = new XmlSerializerNamespaces();
                xs.Add("", "");
                xmlSerializer.Serialize(xmlWriter, xmlObject, xs);
            }
            else
                xmlSerializer.Serialize(xmlWriter, xmlObject);

            return encoding.GetString(memoryStream.ToArray());
        }

        public static void SerializeToXmlFile(T xmlObject, string filename, Encoding encoding, bool removeNamespace)
        {
            // Write the XmlTextWriter's bytes straight to disk. The previous
            // round-trip through File.WriteAllText(path, string) silently
            // dropped the encoding parameter and re-encoded as UTF-8, leaving
            // the on-disk file with an XML declaration that lied about being
            // UTF-16 and an odd byte count that broke downstream parsers.
            var memoryStream = new MemoryStream();
            var xmlWriter = new XmlTextWriter(memoryStream, encoding) { Formatting = Formatting.Indented };

            if (removeNamespace)
            {
                var xs = new XmlSerializerNamespaces();
                xs.Add("", "");
                xmlSerializer.Serialize(xmlWriter, xmlObject, xs);
            }
            else
                xmlSerializer.Serialize(xmlWriter, xmlObject);

            File.WriteAllBytes(filename, memoryStream.ToArray());
        }

        public static T DeserializeFromXmlString(string xml)
        {
            var reader = new StringReader(xml);
            var xmlObject = (T)xmlSerializer.Deserialize(reader);
            return xmlObject;
        }

        public static T DeserializeFromXMLFile(string filename)
        {
            return DeserializeFromXmlString(File.ReadAllText(filename));
        }

    }

}
