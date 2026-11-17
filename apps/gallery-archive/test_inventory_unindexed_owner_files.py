"""Read-only owner inventory validation, no credentials or remote calls."""
import unittest
from inventory_unindexed_owner_files import summarize


def fixture(model="mimmi"):
    catalog={"schema_version":1,"model":model,"albums":[
        {"id":"work-one","images":[
            {"key":"originals/work-one/1.jpg","sha256":"a"*64,"bytes":100},
            {"key":"originals/work-one/2.jpg","sha256":"b"*64,"bytes":200}]}]}
    ls=[{"Path":"metadata/catalog.json","Size":500,"IsDir":False},
        {"Path":"originals/work-one/1.jpg","Size":100,"IsDir":False},
        {"Path":"originals/work-one/new.png","Size":80,"IsDir":False},
        {"Path":"temp/unknown.webp","Size":90,"IsDir":False},
        {"Path":"backup.zip","Size":200,"IsDir":False}]
    return catalog,ls


class ReadOnlyOwnerInventoryTests(unittest.TestCase):
    def test_classify_existing_missing_unindexed_and_backup(self):
        c,ls=fixture()
        r=summarize("mimmi",ls,c)
        self.assertEqual(r["catalog_referenced_files_found"],1)
        self.assertEqual(r["catalog_referenced_files_missing"],1)
        self.assertEqual(r["unindexed_original_image_candidates"],1)
        self.assertEqual(r["unindexed_other_image_candidates"],1)
        self.assertEqual(r["unindexed_archive_candidates"],1)
        self.assertEqual(r["indexed_original_file_bytes_found"],100)
        self.assertTrue(r["read_only"])
        self.assertFalse(r["media_downloaded"])
        self.assertNotIn("originals/work-one",repr(r))

    def test_fail_on_wrong_model_catalog(self):
        c,ls=fixture()
        with self.assertRaisesRegex(ValueError,"MODEL|VERIFIED"):
            summarize("yui",ls,c)

    def test_reject_duplicate_or_unsafe_path(self):
        c,ls=fixture()
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            summarize("mimmi",ls+[ls[1]],c)
        with self.assertRaisesRegex(ValueError,"PATH"):
            summarize("mimmi",ls+[{"Path":"../unsafe.jpg","Size":4}],c)

    def test_catalog_missing_record_path_is_not_silently_counted(self):
        c,ls=fixture()
        del c["albums"][0]["images"][0]["key"]
        r=summarize("mimmi",ls,c)
        self.assertEqual(r["catalog_records_without_valid_original_key"],1)
        self.assertEqual(r["catalog_unique_file_keys"],1)

    def test_wrong_list_shape_fails(self):
        c,ls=fixture()
        with self.assertRaisesRegex(ValueError,"ARRAY"):
            summarize("mimmi",{"items":ls},c)


if __name__=="__main__":
    unittest.main()
