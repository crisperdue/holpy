(function ($) {
    var instructions = [];
    var page_num = 0;
    var index = 0;
    var theory_name = "";  // Name of the current theory file
    var theory_imports = [];  // List of imports of the current theory file
    var result_list = [];  // Content of the current theory file
    var theory_desc = "";  // Description of the theory
    var click_count = 0;
    var proof_id = 0;
    var result_list_dict = {};
    var file_list = [];
    var add_mode = false;
    var items_selected = []; // List of selected items in the displayed theory.

    $(document).ready(function () {
        document.getElementById('left').style.height = (window.innerHeight - 40) + 'px';
    });

    // Load html templates
    $(document).ready(function () {
        var includes = $('[data-include]');
        jQuery.each(includes, function () {
            var file = "../" + $(this).data('include') + '.html';
            $(this).load(file);
        });
    });

    $(function () {
        // Add new tab for editing proofs
        $('#add-cell').on('click', function () {
            page_num++;
            // Add new tab
            var templ_tab = _.template($("#template-tab").html());
            $('#codeTab').append(templ_tab({page_num: page_num, label: ""}));

            // Add CodeMirror textarea
            var templ_codepan = _.template($("#template-codepan").html());
            $('#codeTabContent').append(templ_codepan({page_num: page_num}));

            // Add buttons and location for displaying results
            var templ_rbottom = _.template($("#template-proof-rbottom").html());
            $('div.rbottom').append(templ_rbottom({
                page_num: page_num, proof_id: proof_id, theory_name: theory_name
            }));

            init_editor("code" + page_num);

            $('#codeTab a[href="#code' + page_num + '-pan"]').tab('show');
            $('div#prf' + page_num).addClass('selected').siblings().removeClass('selected');
            $('div#prf' + page_num).show().siblings().hide();
            $('.code-cell').each(function () {
                $(this).removeClass('active');
            });
        });

        $('#right').on('click', '.backward-step', function () {
            apply_backward_step(get_selected_editor(), is_others = true);
        });

        $('#right').on('click', ' .abs-thm .thm-content pre', function () {
            apply_backward_step(get_selected_editor(), is_others = false, select_thm = $(this).index());
        });

        $('#right').on('click', '.forward-step', function () {
            apply_forward_step(get_selected_editor(), is_others = true);
        });

        $('#right').on('click', ' .afs-thm .thm-content pre', function () {
            apply_forward_step(get_selected_editor(), is_others = false, select_thm = $(this).index());
        });

        $('#right').on('click', '.rewrite-goal', function () {
            rewrite_goal(get_selected_editor(), is_others = true);
        });

        $('#right').on('click', ' .rewrite-thm .thm-content pre', function () {
            rewrite_goal(get_selected_editor(), is_others = false, select_thm = $(this).index());
        });

        $('#right').on('click', '#link-backward', function () {
            if (index > 0) {
                index--;
                var instr_output = get_selected_instruction();
                instr_output.innerHTML = instructions[index];
                var instr_no_output = get_selected_instruction_number();
                instr_no_output.innerHTML = (index + 1) + '/' + instructions.length;
            }
        });

        $('#right').on('click', '#link-forward', function () {
            if (index < instructions.length - 1) {
                index++;
                var instr_output = get_selected_instruction();
                instr_output.innerHTML = instructions[index];
                var instr_no_output = get_selected_instruction_number();
                instr_no_output.innerHTML = (index + 1) + '/' + instructions.length;
            }
        });

        $('#add-json').click(function () {
            page_num++;
            init_metadata_area(page_num);
        });

        function init_metadata_area(add_page) {
            var templ_tab = _.template($("#template-tab").html());
            $('#codeTab').append(templ_tab({page_num: add_page, label: "File"}));

            var templ_form = _.template($('#template-file-metadata').html());
            $('#codeTabContent').append(templ_form({add_page: add_page}));

            var templ_rbottom = _.template($('#template-metadata-rbottom').html());
            $('div.rbottom').append(templ_rbottom({add_page: add_page}));

            $('#codeTab a[href="#code' + add_page + '-pan"]').tab('show');
            $('div#prf' + add_page).addClass('selected').siblings().removeClass('selected');
            $('div#prf' + add_page).show().siblings().hide();
            $('.code-cell').each(function () {
                $(this).removeClass('active');
            });
        }

//      click save to create and save json_file metadata;
        $('div.rbottom').on('click', 'button[name="save-json"]', function () {
            var pnum = $(this).attr('id');
            var fname = $('#fname' + pnum).val().trim();
            var imp = $('#imp' + pnum).val().split(',');
            var des = $('#code' + pnum).val().trim();
            var flag = false;
            $.each(file_list, function (i, v) {
                if (v === fname)
                    flag = true;
            });
            if (flag === false)
                file_list.push(fname);
            file_list.sort();
            data = {
                'name': fname,
                'imports': imp,
                'description': des
            };
            $.ajax({
                url: '/api/add-new',
                type: 'PUT',
                data: JSON.stringify(data),
                success: function (res) {
                    alert('保存成功!');
                    display_file_list();
                }
            })
        });

//      tab on the left;
        $('#json-tab1,#json-tab2,#json-tab3').click(function () {
            $(this).css({'background': '#F0F0F0', 'text-align': 'center', 'border-bottom': 'none'});
            $(this).siblings('li').css({
                'background': '#f8f8f8',
                'text-align': 'center',
                'border-bottom': 'solid 1px',
                'border-color': '#B8B8B8'
            });
        });

        $('#json-tab1').click(function () {
            $('div#root-file').show();
            $('div#left_json').hide();
            $('div#variable').hide();
        });

        $('#json-tab2').click(function () {
            $('div#root-file').hide();
            $('div#left_json').show();
            $('div#variable').hide();
        });

        $('#json-tab3').click(function () {
            $('div#root-file').hide();
            $('div#left_json').hide();
            $('div#variable').show();
        });

        // Edit metadata for a file
        $('div#root-file').on('click', 'a[name="edit"]', function () {
            // File's id is "edit[n]"
            var number = Number($(this).attr('id').slice(4,).trim());

            page_num++;
            data = JSON.stringify(file_list[number]);
            init_metadata_area(page_num);
            var form = document.getElementById('edit-metadata-form' + page_num);
            $.ajax({
                url: '/api/edit_jsonFile',
                data: data,
                type: 'POST',
                success: function (res) {
                    form.fname.value = res.name;
                    form.imports.value = res.imports.join(',');
                    form.description.textContent = res.description;
                }
            })
        });

        $('div#root-file').on('click', 'a[name="delete"]', function () {
            var number = Number($(this).attr('id').trim());
            var json_name = $(this).attr('class');
            file_list.splice(number, 1);
            display_file_list();
            save_file_list(json_name);
        });

        $('button#register').click(function () {
            $.ajax({
                url: '/api/register',
                type: 'GET',
                success: function () {
                }
            })
        })

        // Save a single proof to the webpage (not to the json file);
        $('div.rbottom').on('click', 'button.save_proof', function () {
            var file_name = $(this).attr('name').slice(4,);
            var editor_id = get_selected_id();
            var id = Number($(this).attr('id'));
            var proof = cells[editor_id]['proof'];
            var output_proof = [];
            $.each(proof, function (i) {
                output_proof.push({});
                $.extend(output_proof[i], proof[i]);  // perform copy
                output_proof[i]['th'] = output_proof[i]['th_raw'];
                output_proof[i]['th_raw'] = undefined;
                output_proof[i]['args'] = output_proof[i]['args_raw'];
                output_proof[i]['args_raw'] = undefined;
            });
            result_list[id]['proof'] = output_proof;
            result_list[id]['num_gaps'] = cells[editor_id]['num_gaps'];
            result_list_dict[file_name] = result_list;
            display_result_list();
            save_json_file();
        });

        // Convert items in the theory from json format for the web client
        // back to the json format for the file.
        function result_to_output(data) {
            if (data.ty === 'def.ax') {
                delete data.type_hl;
            } else if (data.ty === 'thm' || data.ty === 'thm.ax') {
                delete data.prop_hl;
            } else if (data.ty === 'type.ind') {
                delete data.argsT;
                delete data.ext;
            } else if (data.ty === 'def') {
                delete data.type_hl;
                delete data.prop_hl;
            } else if (data.ty === 'def.ind' || data.ty === 'def.pred') {
                delete data.type_hl;
                delete data.ext;
                for (var i in data.rules) {
                    delete data.rules[i].prop_hl;
                }
            }
        }

//      save all of the edited_tab_data to the json-file;
        function save_editor_data() {
            var copy_res = $.extend(true, [], result_list);
            display_result_list();
            $.each(copy_res, function (i, v) {
                result_to_output(v);
            });
            $.ajax({
                url: '/api/editor_file',
                type: 'PUT',
                data: JSON.stringify({
                    'name': name,
                    'data': copy_res
                }),
                success: function () {
                }
            })
        }

        // Save all changed proof on the webpage to the json-file;
        function save_json_file() {
            var output_list = [];
            for (var d in result_list) {
                output_list[d] = {};
                $.extend(output_list[d], result_list[d]);  // perform copy
                result_to_output(output_list[d]);
            }
            var data = {
                'name': name,
                'data': {
                    'name': theory_name,
                    'imports': theory_imports,
                    'description': theory_desc,
                    'content': output_list
                }
            };
            $.ajax({
                url: "/api/save_file",
                type: "POST",
                data: JSON.stringify(data),
                success: function () {
                }
            });
        }

        //click reset button to reset the thm to the origin status;
        $('div.rbottom').on('click', 'button.reset', function () {
            var id = Number($(this).attr('id'));
            var file_name = $(this).attr('name').slice(5,);
            if (file_name) {
                get_selected_editor().reset = true;
                init_empty_proof(file_name, id);
                get_selected_editor().reset = false;
            }
        });

//      click the tab to show;
        $('#codeTab').on("click", "a", function (e) {
            e.preventDefault();
            var tab_pm = $(this).attr('name');
            $(this).tab('show');
            $('div#prf' + tab_pm).addClass('selected').siblings().removeClass('selected');
            $('div#prf' + tab_pm).show().siblings().hide();
        });

//      set cursor & size;
        $('#codeTab').on('shown.bs.tab', 'a', function (event) {
            if (document.querySelector('.code-cell.active textarea + .CodeMirror')) {
                var editor = document.querySelector('.code-cell.active textarea + .CodeMirror').CodeMirror;
                var rtop = document.querySelector('.rtop');
                editor.focus();
                editor.setCursor(editor.lineCount(), Number.MAX_SAFE_INTEGER);
                editor.setSize("auto", rtop.clientHeight - 40);
                editor.refresh();
            }
        });

//      click x on the tab to close and delete the related tab page;
        $('#codeTab').on('click', 'li button', function () {
            var tabId = $(this).parents('li').children('a').attr('href');
            if ($(this).attr('name') === 'code' + tab_pm)
                var id = get_selected_id();
            delete cells[id];
            var tab_pm = $(this).parents('li').attr('name').slice(4,);
            $('div#prf' + tab_pm).remove();
            $(this).parents('li').remove('li');
            $(tabId).remove();
            $('#codeTab a:first').tab('show');
            $('div.rbottom div:eq(0)').addClass('selected').siblings().removeClass('selected');
            $('div.rbottom div:eq(0)').show().siblings().hide();
        });

        $('#delete-cell').on('click', function () {
            $('.code-cell.selected').remove();
        });

        $('#introduction').on("click", function () {
            introduction(get_selected_editor());
        });

        $('#add-line-after').on("click", function () {
            add_line_after(get_selected_editor());
        });

        $('#apply-backward-step').on("click", function () {
            apply_backward_step(get_selected_editor());
        });

        $('#apply-induction').on("click", function () {
            apply_induction(get_selected_editor());
        });

        $('#rewrite-goal').on("click", function () {
            rewrite_goal(get_selected_editor());
        });

        //click proof then send it to the init; including the save-json-file;
        $('#left_json').on('click', 'a[name="proof"]', function (e) {
            e.stopPropagation();
            proof_id = $(this).attr('id');
            eidt_mode = false;
            var thm_name = $(this).parent().find('span#thm_name').text();
            if (result_list[proof_id]['proof']) {
                $('#add-cell').click();
                setTimeout(function () {
                    $('#codeTab li[name="' + get_selected_id() + '"] span').text(thm_name);
                    init_saved_proof(theory_name, proof_id);
                }, 200);
            } else {
                $('#add-cell').click();
                setTimeout(function () {
                    $('#codeTab li[name="' + get_selected_id() + '"] span').text(thm_name);
                    init_empty_proof(theory_name, proof_id);
                }, 200);
            }
        });

//      click edit then create a tab page for the editing;
        $('#left_json').on('click', 'a[name="edit"]', function (s) {
            s.stopPropagation();
            page_num++;
            var a_ele = $(this);
            init_edit_area(page_num, a_ele);
        });

//      click delete then delete the content from webpage;
        $('#left_json').on('click', 'a[name="del"]', function () {
            var a_id = $(this).attr('id').trim();
            var number = Number(a_id.slice(5,));
            result_list.splice(number, 1);
            display_result_list();
            save_editor_data();
            alert('删除成功！');
        });

//      keypress to display unicode;
        $('#codeTabContent').on('keydown', '.unicode-replace', function (e) {
            var content = $(this).val().trim();
            var id = $(this).attr('id');
            var pos = document.getElementById(id).selectionStart;
            if (pos !== 0 && e.keyCode === 9) {
                var len = '';
                for (var key in replace_obj) {
                    var l = key.length;
                    if (content.substring(pos - l, pos) === key) {
                        if (e && e.preventDefault) {
                            e.preventDefault();
                        } else {
                            window.event.returnValue = false;
                        };
                        len = l;
                        content = content.slice(0, pos - len) + replace_obj[key] + content.slice(pos,);
                    }
                }
                if (len) {
                    $(this).val(content);
                    document.getElementById(id).setSelectionRange(pos - len + 1, pos - len + 1);
                }
            }
        });

//      set the textarea height auto; press tab display unicode;
        $('#codeTabContent').on('input', 'textarea', function () {
            var rows = $(this).val().split('\n').length;
            $(this).attr('rows', rows);
        });

        // Initialize edit area, for both editing an existing item and
        // creating a new item.
        // 
        // page_num: index of the current tab.
        // a_ele: if editing an existing item, id of the current item.
        // data_type: if adding a new item, type of the new item.
        function init_edit_area(page_num, a_ele = '', data_type = '') {
            var data_name = '', data_content = '';
            if (!a_ele) {
                data_name = '', data_content = '', number = '';
            } else {
                number = String(Number(a_ele.attr('id').trim().slice(5,)));
                data_name = result_list[number]['name'];
                data_type = result_list[number]['ty'];
            }

            var templ_tab = _.template($("#template-tab").html());
            $('#codeTab').append(templ_tab({page_num: page_num, label: data_type}));

            if (data_type === 'def.ax') {
                if (number)
                    data_content = result_list[number]['type'];
                else
                    $('#codeTab').find('span#' + page_num).text('constant');
                var templ_edit = _.template($("#template-edit-def-ax").html());
                $('#codeTabContent').append(templ_edit({page_num: page_num}));
                var form = document.getElementById('edit-constant-form' + page_num);
                form.data_name.value = data_name;
                form.data_content.value = data_content;
                $('#codeTab a[href="#code' + page_num + '-pan"]').tab('show');
                if (number)
                    form.number.value = number
                else
                    form.number.value = -1
            }
            if (data_type === 'thm' || data_type === 'thm.ax') {
                var templ_edit = _.template($('#template-edit-thm').html());
                $('#codeTabContent').append(templ_edit({page_num: page_num}));

                var form = document.getElementById('edit-thm-form' + page_num);
                if (data_type === 'thm')
                    form.name.labels[0].textContent = 'Theorem';
                else
                    form.name.labels[0].textContent = 'Axiom';
                if (number) {
                    form.number.value = number;
                    form.name.value = data_name;
                    form.prop.value = result_list[number].prop;
                    vars_lines = []
                    $.each(result_list[number].vars, function (nm, T) {
                        vars_lines.push(nm + ' :: ' + T);
                    });
                    form.vars.rows = vars_lines.length;
                    form.vars.value = vars_lines.join('\n');
                    if (result_list[number].hint_backward === 'true')
                        form.hint_backward.checked = true;
                    if (result_list[number].hint_forward === 'true')
                        form.hint_forward.checked = true;
                    if (result_list[number].hint_rewrite === 'true')
                        form.hint_rewrite.checked = true;
                }
                else {
                    form.number.value = -1;
                }
                $('#codeTab a[href="#code' + page_num + '-pan"]').tab('show');
            }
            if (data_type === 'type.ind') {
                if (number) {
                    var ext = result_list[number]['ext'];
                    var argsT = result_list[number]['argsT'];
                    var data_name = result_list[number].name;
                    var templ_edit = _.template($('#template-edit-type-ind').html());
                    $('#codeTabContent').append(templ_edit({
                        page_num: page_num, ext_output: ext.join('\n')
                    }));
                    var form = document.getElementById('edit-type-form' + page_num);
                    $.each(result_list[number]['constrs'], function (i, v) {
                        var str_temp_var = '';
                        $.each(v.args, function (k, val) {
                            var str_temp_term = '';
                            $.each(argsT[i][k], function (l, vlu) {
                                str_temp_term += vlu[0];
                            });
                            str_temp_var += ' (' + val + ' :: ' + str_temp_term + ')';
                        });
                        data_content += '\n' + v['name'] + str_temp_var;
                    })
                } else
                    $('#codeTab').find('span#' + page_num).text('datatype');
                data_content = $.trim(data_content);
                var i = data_content.split('\n').length;
                $('#codeTab').find('span#' + page_num).text(data_name);

                form.data_name.value = data_name;
                form.data_content.textContent = data_content;
                form.data_content.rows = i;
                if (number)
                    form.number.value = number
                else
                    form.number.value = -1

                $('#codeTab a[href="#code' + page_num + '-pan"]').tab('show');
            }
            if (data_type === 'def.ind' || data_type === 'def.pred' || data_type === 'def') {
                var data_content_list = [];
                var data_new_content = '';
                var data_rule_names = [], data_rule_name = '';
                if (data_type === 'def.ind')
                    var type_name = 'fun';
                else if (data_type === 'def.pred')
                    var type_name = 'inductive';
                else
                    var type_name = 'definition'

                if (number) {
                    var ext = result_list[number];
                    var vars = '';
                    var templ_edit = _.template($('#template-edit-def').html());
                    $('#codeTabContent').append(templ_edit({
                        page_num: page_num, type_name: type_name,
                        ext_output: ext.ext.join('\n')
                    }));
                    var form = document.getElementById('edit-def-form' + page_num);
                    data_name = ext.name + ' :: ' + ext.type;
                    if (ext.rules) {
                        for (var j in ext.rules) {
                            var data_con = '';
                            $.each(ext.rules[j].prop_hl, function (i, val) {
                                data_con += val[0];
                            });
                            data_content_list.push(data_con);
                            data_rule_names.push(ext.rules[j]['name']);
                        }
                    }
                    if (data_type === 'def') {
                        var i = 0;
                        data_content_list.push(ext.prop);
                        for (v in ext.vars) {
                            vars += i + ': ' + v + ':' + ext.vars[v] + '\n';
                            i++;
                        }
                    }
                    for (var i in data_content_list) {
                        data_new_content += i + ': ' + data_content_list[i] + '\n';
                        data_rule_name += i + ': ' + data_rule_names[i] + '\n';
                    }
                    $('#codeTab').find('span#' + page_num).text(ext.name);
                } else
                    $('#codeTab').find('span#' + page_num).text('function');
                form.number.value = number;
                form.data_name.value = data_name;
                form.content.textContent = data_new_content.trim();
                form.content.rows = data_new_content.trim().split('\n').length;
                form.data_vars.textContent = vars.trim();
                form.data_vars.rows = vars.trim().split('\n').length;
                if (data_type === 'def.pred') {
                    form.vars_names.textContent = data_rule_name.trim();
                    form.vars_names.rows = data_rule_name.trim().split('\n').length;
                }
                if (number)
                    form.number.value = number
                else
                    form.number.value = -1
                $('#codeTab a[href="#code' + page_num + '-pan"]').tab('show');
                if (data_type !== 'def')
                    display_lines_number(page_num, number);
            }

            var templ_rbottom = _.template($('#template-edit-rbottom').html());
            $('div.rbottom').append(templ_rbottom({page_num: page_num, data_type: data_type}));

            $('div#prf' + page_num).addClass('selected').siblings().removeClass('selected');
            $('div#prf' + page_num).show().siblings().hide();
        }

//      display vars_content in the textarea;
        function display_lines_number(page_num, number) {
            var data_vars_list = [];
            var data_vars_str = '';
            var form = document.getElementById('edit-def-form' + page_num);
            if (number) {
                $.each(result_list[number]['rules'], function (i, v) {
                    var vars_str = '';
                    for (let key in v.vars) {
                        vars_str += key + ':' + v.vars[key] + '   ';
                    }
                    data_vars_list.push(vars_str);
                });
                $.each(data_vars_list, function (i, v) {
                    data_vars_str += i + ': ' + v + '\n';
                })
            } else {
                data_vars_str += '';
            }
            form.data_vars.value = $.trim(data_vars_str);
            form.data_vars.rows = $.trim(data_vars_str).split('\n').length;
        }

//      click save button on edit tab to save content to the left-json for updating;
        $('div.rbottom').on('click', 'button#save-edit', function () {
            var edit_form = get_selected_edit_form('edit-form');
            var tab_pm = $(this).parent().attr('id').slice(3,);
            var error_id = $(this).next().attr('id').trim();
            var id = tab_pm;
            var ty = $(this).attr('name').trim();
            var number = edit_form.number.value;
            var ajax_data = make_data(edit_form, ty, id, number);
            var prev_list = result_list.slice(0, number);
            ajax_data['file-name'] = theory_name;
            ajax_data['prev-list'] = prev_list;
            $.ajax({
                url: '/api/save_modify',
                type: 'POST',
                data: JSON.stringify(ajax_data),
                success: function (res) {
                    var result_data = res['data'];
                    var error = res['error'];
                    delete result_data['file-name'];
                    delete result_data['prev-list'];
                    if (error.message) {
                        var error_info = error['detail-content'];
                        $('div#' + error_id).find('pre').text(error_info);
                    }
                    else {
                        if (number === '-1') {
                            result_list.push(result_data);
                        } else {
                            delete result_list[number].hint_forward;
                            delete result_list[number].hint_backward;
                            delete result_list[number].hint_rewrite;
                            for (var key in result_data) {
                                result_list[number][key] = result_data[key];
                            }
                        }
                        display_result_list();
                        save_editor_data();
                        alert('保存成功！');
                    }
                }
            });
        });

//      make a strict-type data from editing; id=page_num
        function make_data(form, ty, id, number) {
            var ajax_data = {};
            if (ty === 'def.ax') {
                var data_name = $.trim(form.data_name.value);
                var data_content = $.trim(form.data_content.value);
                ajax_data['ty'] = 'def.ax';
                ajax_data['name'] = data_name;
                ajax_data['type'] = data_content;
            }
            if (ty === 'thm' || ty === 'thm.ax') {
                ajax_data['ty'] = ty;
                ajax_data['name'] = form.name.value;
                ajax_data['prop'] = form.prop.value;
                ajax_data['vars'] = {};
                $.each(form.vars.value.split('\n'), function (i, v) {
                    let [nm, T] = v.split('::');
                    if (nm)
                        ajax_data['vars'][nm.trim()] = T.trim();
                });
                if (form.hint_backward.checked === true)
                    ajax_data['hint_backward'] = 'true';
                if (form.hint_forward.checked ===  true)
                    ajax_data['hint_forward'] = 'true';
                if (form.hint_rewrite.checked ===  true)
                    ajax_data['hint_rewrite'] = 'true';
            }
            if (ty === 'type.ind') {
                var data_name = $.trim(form.data_name.value);
                var data_content = $.trim(form.data_content.value);
                var temp_list = [], temp_constrs = [];
                var temp_content_list = data_content.split(/\n/);
                if (data_name.split(/\s/).length > 1) {
                    temp_list.push(data_name.split(/\s/)[0].slice(1,));
                    ajax_data['name'] = data_name.split(/\s/)[1];
                } else {
                    ajax_data['name'] = data_name;
                }
                $.each(temp_content_list, function (i, v) {
                    var temp_con_list = v.split(') (');
                    var temp_con_dict = {};
                    var arg_name = '', args = [], type = '';
                    if (temp_con_list[0].indexOf('(') > 0) {
                        arg_name = temp_con_list[0].slice(0, temp_con_list[0].indexOf('(') - 1);
                        if (temp_con_list.length > 1) {
                            temp_con_list[0] = temp_con_list[0].slice(temp_con_list[0].indexOf('(') + 1,);
                            temp_con_list[temp_con_list.length - 1] = temp_con_list[temp_con_list.length - 1].slice(0, -1);
                            $.each(temp_con_list, function (i, v) {
                                args.push(v.split(' :: ')[0]);
                                type += v.split(' :: ')[1] + '⇒';
                                if (v.split(' :: ')[1].indexOf('⇒') >= 0) {
                                    type += '(' + v.split(' :: ')[1] + ')' + '⇒'
                                }
                            });
                            type = type + data_name;
                        } else {
                            let vars_ = temp_con_list[0].slice(temp_con_list[0].indexOf('(') + 1, -1).split(' :: ')[0];
                            type = temp_con_list[0].slice(temp_con_list[0].indexOf('(') + 1, -1).split(' :: ')[1];
                            args.push(vars_);
                            type = type + '=>' + data_name;
                        }
                    } else {
                        arg_name = temp_con_list[0];
                        type = ajax_data['name'];
                    }
                    temp_con_dict['type'] = type;
                    temp_con_dict['args'] = args;
                    temp_con_dict['name'] = arg_name;
                    temp_constrs.push(temp_con_dict);
                });
                ajax_data['ty'] = 'type.ind';
                ajax_data['args'] = temp_list;
                ajax_data['constrs'] = temp_constrs;
            }
            if (ty === 'def.ind' || ty === 'def' || ty === 'def.pred') {
                var data_name = $.trim(form.data_name.value);
                var data_content = $.trim(form.content.value);
                var rules_list = [];
                var rules = result_list[number].rules;
                var props_list = data_content.split(/\n/);
                var vars_list = $.trim(form.data_vars.value).split(/\n/);
                if (ty === 'def.pred')
                    var names_list = $.trim(form.vars_names.value).split(/\n/);
                $.each(vars_list, function (i, m) {
                    vars_list[i] = $.trim(m.slice(3,));
                });
                $.each(props_list, function (i, v) {
                    props_list[i] = $.trim(v.slice(3,));
                    if (names_list)
                        names_list[i] = $.trim(names_list[i].slice(3,));
                });
                $.each(props_list, function (i, v) {
                    temp_dict = {}
                    temp_vars = {};
                    if (ty !== 'def' && v && vars_list[i]) {
                        temp_dict['prop'] = v;
                        $.each(vars_list[i].split(/\s\s\s/), function (j, k) {
                            temp_vars[$.trim(k.split(':')[0])] = $.trim(k.split(':')[1]);
                        });
                        if (names_list)
                            temp_dict['name'] = names_list[i];
                    } else if (!v) {
                        return true;
                    }
                    temp_dict['vars'] = temp_vars;
                    rules_list.push(temp_dict);
                    ajax_data['rules'] = rules_list;
                });
                if (ty === 'def') {
                    var temp_vars_ = {};
                    $.each(vars_list, function (j, k) {
                        temp_vars_[$.trim(k.split(':')[0])] = $.trim(k.split(':')[1]);
                    });
                    ajax_data['prop'] = $.trim(props_list[0]);
                    ajax_data['vars'] = temp_vars_;
                }
                ajax_data['ty'] = ty;
                ajax_data['name'] = data_name.split(' :: ')[0];
                ajax_data['type'] = data_name.split(' :: ')[1];
            }
            return ajax_data;
        }

//      click to change left_json content bgcolor
        $('#left_json').on('click','div[name="theories"]',function(){
            var id = $(this).attr('id').slice(3,).trim();
            if (items_selected.indexOf(id) >= 0) {
                var index = items_selected.indexOf(id);
                items_selected.splice(index, 1);
            }
            else {
                items_selected.push(id);
            }
            items_selected.sort();
            display_result_list();
        })

//click DEL to delete yellow left_json content and save to webpage and json file
        $('div.dropdown-menu.Ctrl a[name="del"]').on('click',function(){
            $.each(items_selected, function (i, v) {
                result_list[v] = '';
            })
            result_list = result_list.filter(function(item) {
                return item !== '';
            });
            save_editor_data();
            display_result_list();
        })

        function exchange_up(number) {
            var m = 1;
            number = Number(number);
            if (number >0 && number < result_list.length ) {
                var temp = result_list[number];
                result_list[number] = result_list[number - m];
                result_list[number-m] = temp;
                save_editor_data();
                display_result_list();
            }
        }


 //click UP to move up the yellow left_json content and save to webpage and json file
        $('div.dropdown-menu.Ctrl a[name="up"]').on('click', function(){
            $.each(items_selected, function (i, v) {
                var n = 1;
                var temp = v;
                if(result_list[0]['ty'] === 'header'){
                    if (v > String(1)) {
                        items_selected[i] = String(Number(v) - n);
                        exchange_up(temp);
                    }
                }
                else {
                    if (v > String(0)) {
                        items_selected[i] = String(Number(v) - n);
                        exchange_up(temp);
                    }
                }
            })
        })

        function exchange_down(number) {
            var m = 1;
            number = Number(number);
            if (number >=0 && number < result_list.length) {
                var temp = result_list[number];
                result_list[number] = result_list[number + m];
                result_list[number + m] = temp;
                save_editor_data();
                display_result_list();
            }
        }

//click down to move down the yellow left_json content and save to webpage and json file
        $('div.dropdown-menu.Ctrl a[name="down"]').on('click', function(){
            for (let i = items_selected.length-1;i >= 0;i--) {
                var temp = items_selected[i];
                var n = 1;
                items_selected[i] = String(Number(temp) + n);
                exchange_down(temp);
            }
        })

        // Open json file with the given name.
        function open_json_file(name) {
            items_selected = [];
            $('#json-tab2').click();
            $('#left_json').empty();
            var data = JSON.stringify(name);
            load_json_file(data);
            add_mode = true;
        }

        // Open json file from links in the 'Files' tab.
        $('#root-file').on('click', 'a[name="file"]', function () {
            open_json_file($(this).text().trim());
        });

        // Open json file from menu.
        $('#json-button').on('click', function () {
            var name = prompt('Please enter the file name');
            if (name !== null) {
                open_json_file(name);
            }
        });

        $('div.dropdown-menu.add-info a').on('click', function () {
            if (add_mode === true) {
                page_num++;
                var ty = $(this).attr('name');
                init_edit_area(page_num, '', ty);
            }
        });

        // On loading page, obtain list of theories.
        $.ajax({
            url: "/api/find_files",
            success: function (res) {
                $('#json-tab1').click();
                file_list = res.theories;
                display_file_list();
            }
        });
    });

    function display_file_list() {
        $(function () {
            $('#root-file').html('');
            var templ = _.template($("#template-file-list").html());
            $('#root-file').append(templ({file_list: file_list}));    
        });
    }

    function save_file_list(file_name) {
        $.ajax({
            url: '/api/save_file_list',
            data: JSON.stringify(file_name),
            type: 'PUT',
            success: function (res) {
                alert('删除成功！');
            }
        })
    }

    // Initialize empty proof for the theorem with given file name and item_id.
    function init_empty_proof(file_name, item_id) {
        r_data = result_list_dict[file_name][item_id]
        var event = {
            'id': get_selected_id(),
            'vars': r_data['vars'],
            'prop': r_data['prop'],
            'theory_name': file_name,
            'thm_name': r_data['name']
        };
        var data = JSON.stringify(event);
        display_running();
        $.ajax({
            url: "/api/init-empty-proof",
            type: "POST",
            data: data,
            success: function (result) {
                clear_match_thm();
                display_checked_proof(result);
                display_instructions(r_data.instructions);
            }
        });
    }

    // Load saved proof for the theorem with given file name and item_id.
    function init_saved_proof(file_name, item_id) {
        r_data = result_list_dict[file_name][item_id]
        var event = {
            'id': get_selected_id(),
            'vars': r_data['vars'],
            'proof': r_data['proof'],
            'theory_name': file_name,
            'thm_name': r_data['name']
        };
        var data = JSON.stringify(event);
        display_running();
        $.ajax({
            url: "/api/init-saved-proof",
            type: 'POST',
            data: data,
            success: function (result) {
                display_checked_proof(result);
                display_instructions(r_data.instructions);
            }
        })
    }

    // Display result_list on the left side of the page.
    function display_result_list() {
        result_list_dict[theory_name] = result_list;
        var import_str = theory_imports.join(' ');
        $('#left_json').html('');
        var templ = _.template($("#template-content-theory_desc").html());
        $('#left_json').append(templ({
            theory_desc: theory_desc, import_str: import_str
        }));
        $.each(result_list, function(num, ext) {
            var class_item = '';
            if (items_selected.indexOf(String(num)) >= 0) {
                class_item = 'selected_item';
            }
            var templ = $("#template-content-" + ext.ty.replace(".", "-"));
            $('#left_json').append(_.template(templ.html())({
                num: num, ext: ext, class_item: class_item
            }));
        });
    }

    // Load json file from server and display the results.
    function load_json_file(data) {
        $.ajax({
            url: "/api/load-json-file",
            type: "POST",
            data: data,
            success: function (result) {
                theory_name = result.data.name;
                theory_imports = result.data.imports;
                theory_desc = result.data.description;

                if (theory_name in result_list_dict) {
                    result_list = result_list_dict[theory_name];
                } else {
                    result_list = result.data.content;
                }
                display_result_list();
            }
        });
    }

    function init_editor(id) {
        var editor = CodeMirror.fromTextArea(document.getElementById(id), {
            mode: "text/x-python",
            lineNumbers: true,
            firstLineNumber: 0,
            theme: "",
            lineWrapping: false,
            foldGutter: true,
            smartIndent: false,
            matchBrackets: true,
            viewportMargin: Infinity,
            scrollbarStyle: "overlay",
            gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
            extraKeys: {
                "Ctrl-I": introduction,
                "Ctrl-B": apply_backward_step,
                "Ctrl-R": rewrite_goal,
                "Ctrl-F": apply_forward_step,
                "Ctrl-Q": function (cm) {
                    cm.foldCode(cm.getCursor());
                }
            }
        });
        var rtop = document.querySelector('.rtop');
        editor.setSize("auto", rtop.clientHeight - 40);
        editor.setValue("");
        cells[id] = {
            theory_name: theory_name,
            facts: new Set(),
            goal: -1,
            edit_line_number: -1,
        };
        editor.on("keydown", function (cm, event) {
            let line_no = cm.getCursor().line;
            let line = cm.getLine(line_no);
            if (event.code === 'Enter') {
                event.preventDefault();
                if (cells[id].edit_line_number !== -1) {
                    set_line(cm);
                } else {
                    add_line_after(cm);
                }
            } else if (event.code === 'Tab') {
                event.preventDefault();
                unicode_replace(cm);
            } else if (event.code === 'Backspace') {
                if (line.trim() === '') {
                    event.preventDefault();
                    remove_line(cm);
                }
            } else if (event.code === 'Escape') {
                event.preventDefault();
                if (cells[id].edit_line_number !== -1) {
                    cm.getAllMarks().forEach(e => {
                        if (e.readOnly !== undefined) {
                            if (e.readOnly) {
                                e.clear();
                            }
                        }
                    });
                    var origin_line = display_line(cells[id]['proof'][cells[id].edit_line_number]);
                    cm.replaceRange(origin_line, {line: cells[id].edit_line_number, ch: 0}, {
                        line: cells[id].edit_line_number,
                        ch: Number.MAX_SAFE_INTEGER
                    });
                    cells[id].edit_line_number = -1;
                }
            }
        });

        editor.on("focus", function (cm, event) {
            $('#codeTabContent .code-cell').each(function () {
                $(this).removeClass('selected');
            });
            $(cm.getTextArea().parentNode).addClass('selected');
        });

        editor.on("cursorActivity", function (cm) {
            if (is_mousedown) {
                mark_text(cm);
                match_thm();
                is_mousedown = false;
            }
        });

        editor.on('beforeChange', function (cm, change) {
            if (!edit_flag &&
                cells[get_selected_id()].edit_line_number !== change.from.line) {
                change.cancel();
            }
        });

        editor.on('mousedown', function (cm, event) {
            var timer = 0;
            is_mousedown = true;
            click_count++;
            if (click_count === 1) {
                timer = setTimeout(function () {
                    if (click_count > 1) {
                        clearTimeout(timer);
                        set_read_only(cm);
                    }
                    click_count = 0;
                }, 300)
            }
        });
    }

    function set_read_only(cm) {
        cm.setCursor(cm.getCursor().line, Number.MAX_SAFE_INTEGER);
        var line_num = cm.getCursor().line;
        var ch = cm.getCursor().ch;
        var line = cm.getLineHandle(line_num).text;
        var id = get_selected_id();
        if (line.indexOf('sorry') !== -1) {
            cm.addSelection({line: line_num, ch: ch - 5}, {line: line_num, ch: ch});
            cells[id].edit_line_number = line_num;
        } else if (line.trim() === '') {
            cells[id].edit_line_number = line_num;
        }
    }

    function mark_text(cm) {
        var line_num = cm.getCursor().line;
        var line = cm.getLineHandle(line_num).text;
        var id = get_selected_id();
        if (line.indexOf('sorry') !== -1) {
            // Choose a new goal
            cells[id].goal = line_num;
        }
        else if (cells[id].goal !== -1) {
            // Choose or unchoose a fact
            if (cells[id].facts.has(line_num))
                cells[id].facts.delete(line_num)
            else
                cells[id].facts.add(line_num)
        }
        display_facts_and_goal(cm);
        clear_match_thm();
    }

    function resize_editor() {
        var editor = document.querySelector('.code-cell.selected textarea + .CodeMirror').CodeMirror;
        var rtop = document.querySelector('.rtop');
        editor.setSize("auto", rtop.clientHeight - 40);
        editor.refresh();
    }

    Split(['.rtop', '.rbottom'], {
        sizes: [70, 50],
        direction: 'vertical',
        minSize: 39,
        onDrag: resize_editor,
        gutterSize: 2,
    });
    Split(['.left', '.right'], {
        sizes: [30, 70],
        gutterSize: 2,
    });
})(jQuery);
