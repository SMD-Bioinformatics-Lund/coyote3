

class AnnotationsHandler:

    def get_global_annotations( self, variant, assay, subpanel ):
        genomic_location = str(variant["CHROM"]) + ":" + str(variant["POS"]) + ":" + variant["REF"] + "/" + variant["ALT"]
        if len( variant["INFO"]["selected_CSQ"]["HGVSp"] ) > 0:
            annotations = self.annotations_collection.find( { 'gene': variant["INFO"]["selected_CSQ"]["SYMBOL"], '$or': [
                { 'nomenclature': 'p', 'variant': no_transid( variant["INFO"]["selected_CSQ"]["HGVSp"] ) },
                { 'nomenclature': 'c', 'variant': no_transid( variant["INFO"]["selected_CSQ"]["HGVSc"] ) },
                { 'nomenclature': 'g', 'variant': genomic_location } ]
            }).sort( 'time_created', 1 )
        elif len( variant["INFO"]["selected_CSQ"]["HGVSc"] ) > 0:
            annotations = self.annotations_collection.find( { 'gene': variant["INFO"]["selected_CSQ"]["SYMBOL"], '$or': [
                { 'nomenclature': 'c', 'variant': no_transid( variant["INFO"]["selected_CSQ"]["HGVSc"] ) },
                { 'nomenclature': 'g', 'variant': genomic_location } ] 
            }).sort( 'time_created', 1 )
        else:
            annotations = self.annotations_collection.find( { 'nomenclature': 'g', 'variant': genomic_location } ).sort( 'time_created', 1 )
    
        latest_classification = {'class':999}
        latest_classification_other = {}
        annotations_arr = []
        annotations_interesting = {}

        for anno in annotations:
            if 'class' in  anno:
                ## collect latest for current assay (if latest not assigned pick that)
                ## also collect latest anno for all other assigned assays (including non-assays)
                ## special rule for assays with subpanels, solid, tumwgs maybe lymph?
                try:
                    if assay == "solid":
                        if anno['assay'] == assay and anno['subpanel'] == subpanel:
                            latest_classification = anno
                        else:
                            ass_sub = anno['assay'] + ":" + anno['subpanel']
                            latest_classification_other[ass_sub] = anno['class']
                    else:
                        if anno['assay'] == assay:
                            latest_classification = anno
                        else:
                            ass_sub = anno['assay'] + ":" + anno['subpanel']
                            latest_classification_other[ass_sub] = anno['class']
                except:
                    latest_classification = anno
                    latest_classification_other['N/A'] = anno['class']
            elif 'text' in anno:
                try:
                    if assay == "solid":
                        if anno['assay'] == assay and anno['subpanel'] == subpanel:
                            ass_sub = anno['assay'] + ":" + anno['subpanel']
                            annotations_interesting[ass_sub] = anno
                            annotations_arr.append(anno)
                        else:
                            annotations_arr.append(anno)
                    else:
                        if anno['assay'] == assay:
                            annotations_interesting[anno['assay']] = anno
                            annotations_arr.append(anno)
                        else:
                            annotations_arr.append(anno)
                except:
                    annotations_arr.append(anno)

        
        latest_other_arr = []
        for latest_assay in latest_classification_other:
            assay_sub = latest_assay.split(':')
            try:
                a = assay_sub[1]
            except:
                assay_sub.append(None)
            latest_other_arr.append({'assay': assay_sub[0], 'class':latest_classification_other[latest_assay], 'subpanel':assay_sub[1]})

        return annotations_arr, latest_classification, latest_other_arr, annotations_interesting
    
    def no_transid(self, nom):
        a = nom.split(':')
        if 1 < len(a):
            return a[1]
        return nom