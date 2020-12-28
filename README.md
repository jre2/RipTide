# RipTide

## TODO
we found a case where request vs delivered quality assert failed
	figure out how we want to handle those albums

### Changes to data collection
* ??? Consider just saving ALL json data from every API pull, in case we change our mind on what to save later, so we don't ever have to redo API requests
    * API requests are presumably the #1 thing to limit to avoid getting banned
* Track what albums we've downloaded (and maybe when/where) so work can done on different machines (or eventually made parallel) more easily

* Better error handling and recovery from http errors mid update
* Better way to handle resuming partially updated album, stale database, etc

### Changes to tagging
* ??? Consider: DATE should be YYYY-MM-DD instead of YYYY
    * We already cannot trust all DATE entries will be perfectly normalized, so we need to interpret and extract Year for path naming purposes anyway

* Save tags with more useful information
    * Source:Tidal      # or MediaType: WEB WebSource: Tidal or something along those lines
    * TidalArtistId, TidalAlbumId, TidalTrackId, TidalStreamTimeStamp, TidalStreamQuality
        * we could track stream timestamp and quality in separate database, but that's fragile
        * ids might change, but they're still fairly useful for cross referencing
        * stream timestamp is dangerous for sharing, but accoustic watermark is just as real of a problem
    * ??? CatalogueNumber   (not availble?)
    * ??? bit depth, sampling rate (this can be retrieved from the file in other ways, just slightly less easily)

* ??? Should BARCODE=888735898624 instead be BARCODE=upc:888735898624  (to help distinguish UPC, EAN, etc)

### Changes to pulling
* Save cover art (but don't embed)
* Improve escaping: ～？！＄＃「」＜＞
* ??? Consider: split multiple disc albums into separate directories
